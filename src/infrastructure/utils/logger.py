"""
Structured Logger - 结构化日志系统

提供 JSON 格式的结构化日志输出，支持：
- 线程安全的日志记录
- 中文输出
- 额外字段通过 **kwargs 传递
- 敏感信息自动脱敏
- 与 Python 标准 logging 模块兼容
"""

import json
import logging
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union


SENSITIVE_FIELDS = {
    'password', 'passwd', 'pwd',
    'token', 'access_token', 'refresh_token', 'auth_token',
    'secret', 'secret_key', 'api_key', 'apikey',
    'private_key', 'privatekey',
    'credential', 'credentials',
    'session_id', 'sessionid',
    'authorization', 'auth',
}

SENSITIVE_PATTERNS = [
    (re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^"\',\s]+)', re.IGNORECASE), r'\1***'),
    (re.compile(r'(token["\']?\s*[:=]\s*["\']?)([^"\',\s]+)', re.IGNORECASE), r'\1***'),
    (re.compile(r'(secret["\']?\s*[:=]\s*["\']?)([^"\',\s]+)', re.IGNORECASE), r'\1***'),
    (re.compile(r'(api_key["\']?\s*[:=]\s*["\']?)([^"\',\s]+)', re.IGNORECASE), r'\1***'),
]

MASK_VALUE = '***'


def sanitize_value(key: str, value: Any) -> Any:
    """
    对敏感字段的值进行脱敏处理
    
    Args:
        key: 字段名
        value: 字段值
        
    Returns:
        脱敏后的值
    """
    if not isinstance(key, str):
        return value
    
    key_lower = key.lower().replace('-', '_')
    
    for sensitive in SENSITIVE_FIELDS:
        if sensitive in key_lower:
            return MASK_VALUE
    
    if isinstance(value, str):
        for pattern, replacement in SENSITIVE_PATTERNS:
            if pattern.search(value):
                value = pattern.sub(replacement, value)
    
    return value


def sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    递归脱敏字典中的敏感信息
    
    Args:
        data: 原始字典
        
    Returns:
        脱敏后的字典
    """
    if not isinstance(data, dict):
        return data
    
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = sanitize_dict(value)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict(item) if isinstance(item, dict) else sanitize_value(key, item)
                for item in value
            ]
        else:
            result[key] = sanitize_value(key, value)
    
    return result


class JsonFormatter(logging.Formatter):
    """JSON 格式化器，用于结构化日志输出"""

    def __init__(self, ensure_ascii: bool = False, indent: Optional[int] = None):
        super().__init__()
        self.ensure_ascii = ensure_ascii
        self.indent = indent
        self._lock = threading.Lock()

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "logger": record.name,
        }

        if hasattr(record, "extra_fields") and record.extra_fields:
            log_entry["extra"] = record.extra_fields

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            log_entry["stack_trace"] = self.formatStack(record.stack_info)

        with self._lock:
            return json.dumps(log_entry, ensure_ascii=self.ensure_ascii, indent=self.indent)


class TextFormatter(logging.Formatter):
    """文本格式化器，用于可读性更好的日志输出"""

    DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(
        self, fmt: Optional[str] = None, datefmt: Optional[str] = None, include_extra: bool = True
    ):
        super().__init__(fmt or self.DEFAULT_FORMAT, datefmt or self.DEFAULT_DATE_FORMAT)
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)

        if self.include_extra and hasattr(record, "extra_fields") and record.extra_fields:
            extra_str = " | ".join(f"{k}={v}" for k, v in record.extra_fields.items())
            formatted = f"{formatted} | {extra_str}"

        return formatted


class StructuredLogger:
    """结构化日志记录器

    提供线程安全的结构化日志记录功能，支持 JSON 和文本格式输出。

    Example:
        >>> logger = get_logger("my_module")
        >>> logger.info("任务开始执行", task_id="123", user="张三")
        >>> logger.error("处理失败", error_code=500, details="连接超时")
    """

    def __init__(
        self,
        name: str,
        level: int = logging.INFO,
        json_output: bool = True,
        output_file: Optional[Union[str, Path]] = None,
        console_output: bool = True,
        ensure_ascii: bool = False,
    ):
        self._name = name
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._logger.handlers.clear()
        self._lock = threading.RLock()

        self._json_output = json_output
        self._ensure_ascii = ensure_ascii

        if console_output:
            self._add_console_handler(level)

        if output_file:
            self._add_file_handler(output_file, level)

    def _add_console_handler(self, level: int) -> None:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        if self._json_output:
            console_handler.setFormatter(JsonFormatter(ensure_ascii=self._ensure_ascii))
        else:
            console_handler.setFormatter(TextFormatter())

        self._logger.addHandler(console_handler)

    def _add_file_handler(self, output_file: Union[str, Path], level: int) -> None:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(output_path, mode="a", encoding="utf-8")
        file_handler.setLevel(level)

        if self._json_output:
            file_handler.setFormatter(JsonFormatter(ensure_ascii=self._ensure_ascii))
        else:
            file_handler.setFormatter(TextFormatter())

        self._logger.addHandler(file_handler)

    def _log(self, level: int, message: str, exc_info: bool = False, **kwargs: Any) -> None:
        sanitized_kwargs = sanitize_dict(kwargs) if kwargs else {}
        extra = {"extra_fields": sanitized_kwargs} if sanitized_kwargs else {}

        with self._lock:
            self._logger.log(level, message, exc_info=exc_info, extra=extra)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs: Any) -> None:
        self._log(logging.ERROR, message, exc_info=exc_info, **kwargs)

    def critical(self, message: str, exc_info: bool = False, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, message, exc_info=exc_info, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, message, exc_info=True, **kwargs)

    def set_level(self, level: int) -> None:
        with self._lock:
            self._logger.setLevel(level)
            for handler in self._logger.handlers:
                handler.setLevel(level)

    def get_logger_name(self) -> str:
        return self._name

    def get_standard_logger(self) -> logging.Logger:
        return self._logger


_loggers: dict[str, StructuredLogger] = {}
_loggers_lock = threading.Lock()

_default_config = {
    "level": logging.INFO,
    "json_output": True,
    "console_output": True,
    "output_file": None,
    "ensure_ascii": False,
}


def configure_logging(
    level: int = logging.INFO,
    json_output: bool = True,
    console_output: bool = True,
    output_file: Optional[Union[str, Path]] = None,
    ensure_ascii: bool = False,
) -> None:
    global _default_config
    _default_config = {
        "level": level,
        "json_output": json_output,
        "console_output": console_output,
        "output_file": output_file,
        "ensure_ascii": ensure_ascii,
    }


def get_logger(
    name: str,
    level: Optional[int] = None,
    json_output: Optional[bool] = None,
    output_file: Optional[Union[str, Path]] = None,
    console_output: Optional[bool] = None,
    ensure_ascii: Optional[bool] = None,
) -> StructuredLogger:
    with _loggers_lock:
        if name in _loggers:
            return _loggers[name]

        config = {
            "level": level if level is not None else _default_config["level"],
            "json_output": (
                json_output if json_output is not None else _default_config["json_output"]
            ),
            "console_output": (
                console_output if console_output is not None else _default_config["console_output"]
            ),
            "output_file": (
                output_file if output_file is not None else _default_config["output_file"]
            ),
            "ensure_ascii": (
                ensure_ascii if ensure_ascii is not None else _default_config["ensure_ascii"]
            ),
        }

        logger = StructuredLogger(name=name, **config)
        _loggers[name] = logger
        return logger


def get_standard_logger(name: str) -> logging.Logger:
    structured_logger = get_logger(name)
    return structured_logger.get_standard_logger()

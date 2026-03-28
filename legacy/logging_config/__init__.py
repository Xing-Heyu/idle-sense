"""
Logging configuration module.

Provides centralized logging configuration for the entire project.
"""

import io
import json
import logging
import logging.handlers
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


JSON_FORMAT = {
    "timestamp": "asctime",
    "level": "levelname",
    "logger": "name",
    "message": "message",
    "module": "module",
    "function": "funcName",
    "line": "lineno",
}


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": getattr(record, "module", ""),
            "function": getattr(record, "funcName", ""),
            "line": record.lineno,
        }
        return json.dumps(log_entry)


class ContextFilter(logging.Filter):
    """Filter to add contextual information to log records."""

    def filter(self, record: logging.LogRecord) -> logging.LogRecord:
        record.module = record.name.split(".")[0] if record.name else ""
        return record


class RotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Rotating file handler with retention policy."""

    def __init__(
        self,
        filename: str,
        mode: str = "a",
        maxBytes: int = 10 * 1024 * 1024,
        backupCount: int = 5,
        encoding: str = "utf-8",
        delay: bool = True
    ):
        super().__init__(
            filename,
            mode=mode,
            maxBytes=maxBytes,
            backupCount=backupCount,
            encoding=encoding,
            delay=delay
        )


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    log_dir: str = "logs",
    json_logging: bool = False,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    context_filter: bool = True
) -> logging.Logger:
    """Setup centralized logging configuration."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path / log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
            delay=True
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        if json_logging:
            json_file = log_path.with_suffix(".json")
            json_handler = logging.FileHandler(json_file, mode="a", encoding="utf-8")
            json_handler.setLevel(level)
            json_handler.setFormatter(JsonFormatter())
            root_logger.addHandler(json_handler)

        if context_filter:
            root_logger.addFilter(ContextFilter())

    return root_logger


def get_logger(name: str, level: int = None) -> logging.Logger:
    """Get a logger instance for a module."""
    logger = logging.getLogger(name)
    if level is not None:
        logger.setLevel(level)
    return logger


def log_exception(
    logger: logging.Logger,
    message: str,
    exception: Exception,
    exc_info: Optional[dict[str, Any]] = None,
    level: int = logging.ERROR,
    include_traceback: bool = True,
    context: Optional[dict[str, Any]] = None
) -> None:
    """Log an exception with full context."""
    exc_str = str(exception)

    if exc_info:
        exc_str += f"\nException Info: {json.dumps(exc_info, indent=2)}"

    if context:
        exc_str += f"\nContext: {json.dumps(context, indent=2)}"

    if include_traceback:
        tb = io.StringIO()
        traceback.print_exception(
            type(exception),
            exception,
            exception.__traceback__,
            file=tb
        )
        exc_str += f"\nTraceback:\n{tb.getvalue()}"

    logger.log(level, f"{message}\n{exc_str}")


class LoggingContext:
    """Context manager for temporary logging configuration."""

    def __init__(
        self,
        logger: logging.Logger,
        level: int = None,
        handler: logging.Handler = None
    ):
        self.logger = logger
        self.original_level = logger.level
        self.original_handlers = logger.handlers[:]
        self.temp_level = level
        self.temp_handler = handler

    def __enter__(self):
        if self.temp_level is not None:
            self.logger.setLevel(self.temp_level)
        if self.temp_handler is not None:
            self.logger.addHandler(self.temp_handler)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.original_level)
        self.logger.handlers = self.original_handlers
        return False


def suppress_logging(logger_name: str) -> LoggingContext:
    """Suppress logging for a specific logger."""
    return LoggingContext(logging.getLogger(logger_name), level=logging.CRITICAL)


def verbose_logging(logger_name: str) -> LoggingContext:
    """Enable verbose logging for a specific logger."""
    return LoggingContext(logging.getLogger(logger_name), level=logging.DEBUG)


logger = get_logger(__name__)

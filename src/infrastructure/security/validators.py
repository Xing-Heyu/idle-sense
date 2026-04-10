"""
输入验证器模块

提供代码安全验证、任务输入验证和用户输入验证功能
"""

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ValidationResult:
    """验证结果数据类"""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """添加错误信息"""
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str) -> None:
        """添加警告信息"""
        self.warnings.append(message)

    def merge(self, other: "ValidationResult") -> None:
        """合并另一个验证结果"""
        if not other.valid:
            self.valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class InputValidator:
    """输入验证器类"""

    DANGEROUS_PATTERNS: list[str] = [
        r"__import__\s*\(",
        r"\beval\s*\(",
        r"\bexec\s*\(",
        r"os\.system\s*\(",
        r"os\.popen\s*\(",
        r"subprocess\.",
        r"commands\.",
        r"pickle\.loads?\s*\(",
        r"marshal\.loads?\s*\(",
        r"shelve\.open\s*\(",
        r"importlib\.",
        r"import\s+os\b",
        r"import\s+sys\b",
        r"import\s+subprocess\b",
        r"import\s+socket\b",
        r"from\s+os\b",
        r"from\s+sys\b",
        r"from\s+subprocess\b",
        r"from\s+socket\b",
        r"open\s*\([^)]*[\'\"]w[\'\"]",
        r"open\s*\([^)]*[\'\"]a[\'\"]",
        r"\.write\s*\(",
        r"\.remove\s*\(",
        r"\.unlink\s*\(",
        r"shutil\.rmtree",
        r"os\.remove",
        r"os\.unlink",
        r"os\.rmdir",
        r"os\.makedirs",
        r"os\.mkdir",
        r"__builtins__",
        r"__globals__",
        r"__code__",
        r"__class__",
        r"__base__",
        r"__bases__",
        r"__subclasses__",
        r"__mro__",
        r"globals\s*\(",
        r"locals\s*\(",
        r"vars\s*\(",
        r"dir\s*\(",
        r"getattr\s*\(",
        r"setattr\s*\(",
        r"delattr\s*\(",
        r"hasattr\s*\(",
        r"compile\s*\(",
        r"breakpoint\s*\(",
        r"input\s*\(",
        r"exit\s*\(",
        r"quit\s*\(",
    ]

    DEFAULT_MAX_CODE_LENGTH: int = 100000
    DEFAULT_MAX_STRING_LENGTH: int = 10000

    def __init__(
        self,
        max_code_length: int = DEFAULT_MAX_CODE_LENGTH,
        max_string_length: int = DEFAULT_MAX_STRING_LENGTH,
        custom_dangerous_patterns: Optional[list[str]] = None,
    ):
        self.max_code_length = max_code_length
        self.max_string_length = max_string_length
        self._dangerous_patterns = self.DANGEROUS_PATTERNS.copy()
        if custom_dangerous_patterns:
            self._dangerous_patterns.extend(custom_dangerous_patterns)
        self._compiled_patterns: list[re.Pattern] = [
            re.compile(pattern) for pattern in self._dangerous_patterns
        ]

    def validate_code(
        self,
        code: str,
        max_length: Optional[int] = None,
    ) -> ValidationResult:
        """
        验证代码安全性

        Args:
            code: 要验证的代码字符串
            max_length: 最大代码长度限制，默认使用实例配置

        Returns:
            ValidationResult: 验证结果
        """
        result = ValidationResult(valid=True)
        max_len = max_length or self.max_code_length

        if not code or not code.strip():
            result.add_error("代码不能为空")
            return result

        if len(code) > max_len:
            result.add_error(f"代码长度超过限制: {len(code)} > {max_len}")
            return result

        for pattern in self._compiled_patterns:
            matches = pattern.findall(code)
            if matches:
                result.add_error(f"检测到危险代码模式: {pattern.pattern}")

        try:
            ast.parse(code)
        except SyntaxError as e:
            result.add_error(f"代码语法错误: {e.msg} (行 {e.lineno})")

        self._check_ast_nodes(code, result)

        return result

    def _check_ast_nodes(self, code: str, result: ValidationResult) -> None:
        """检查 AST 节点的安全性"""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return

        dangerous_builtins = {
            "eval",
            "exec",
            "compile",
            "input",
            "open",
            "__import__",
            "globals",
            "locals",
            "vars",
            "dir",
            "getattr",
            "setattr",
            "delattr",
            "hasattr",
            "breakpoint",
            "memoryview",
        }

        dangerous_attrs = {
            "__class__",
            "__base__",
            "__bases__",
            "__subclasses__",
            "__mro__",
            "__init__",
            "__new__",
            "__del__",
            "__getattribute__",
            "__setattr__",
            "__delattr__",
            "__dict__",
            "__globals__",
            "__code__",
            "__builtins__",
        }

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in dangerous_builtins
            ):
                result.add_error(f"禁止调用危险函数: {node.func.id}")

            elif isinstance(node, ast.Attribute):
                if node.attr in dangerous_attrs:
                    result.add_error(f"禁止访问危险属性: {node.attr}")

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split(".")[0]
                    if module_name in {"os", "sys", "subprocess", "socket", "pickle", "marshal"}:
                        result.add_error(f"禁止导入危险模块: {module_name}")

            elif isinstance(node, ast.ImportFrom) and node.module:
                module_name = node.module.split(".")[0]
                if module_name in {"os", "sys", "subprocess", "socket", "pickle", "marshal"}:
                    result.add_error(f"禁止从危险模块导入: {module_name}")

    def validate_task_input(
        self,
        data: dict[str, Any],
        schema: dict[str, Any],
    ) -> ValidationResult:
        """
        验证任务输入数据

        Args:
            data: 要验证的数据字典
            schema: 验证模式，格式如下:
                {
                    "field_name": {
                        "type": type,  # 期望的类型
                        "required": bool,  # 是否必需
                        "min": int/float,  # 最小值（可选）
                        "max": int/float,  # 最大值（可选）
                        "min_length": int,  # 最小长度（可选）
                        "max_length": int,  # 最大长度（可选）
                        "choices": list,  # 允许的值列表（可选）
                        "pattern": str,  # 正则表达式模式（可选）
                        "custom": Callable,  # 自定义验证函数（可选）
                    }
                }

        Returns:
            ValidationResult: 验证结果
        """
        result = ValidationResult(valid=True)

        if not isinstance(data, dict):
            result.add_error("输入数据必须是字典类型")
            return result

        for field_name, field_schema in schema.items():
            field_result = self._validate_field(
                data.get(field_name),
                field_name,
                field_schema,
            )
            result.merge(field_result)

        return result

    def _validate_field(
        self,
        value: Any,
        field_name: str,
        schema: dict[str, Any],
    ) -> ValidationResult:
        """验证单个字段"""
        result = ValidationResult(valid=True)
        required = schema.get("required", False)

        if value is None:
            if required:
                result.add_error(f"必需字段缺失: {field_name}")
            return result

        expected_type = schema.get("type")
        if expected_type and not isinstance(value, expected_type):
            result.add_error(
                f"字段 '{field_name}' 类型错误: 期望 {expected_type.__name__}, "
                f"实际 {type(value).__name__}"
            )
            return result

        if isinstance(value, (int, float)):
            min_val = schema.get("min")
            max_val = schema.get("max")
            if min_val is not None and value < min_val:
                result.add_error(f"字段 '{field_name}' 值 {value} 小于最小值 {min_val}")
            if max_val is not None and value > max_val:
                result.add_error(f"字段 '{field_name}' 值 {value} 大于最大值 {max_val}")

        if isinstance(value, (str, list)):
            min_len = schema.get("min_length")
            max_len = schema.get("max_length")
            length = len(value)
            if min_len is not None and length < min_len:
                result.add_error(f"字段 '{field_name}' 长度 {length} 小于最小长度 {min_len}")
            if max_len is not None and length > max_len:
                result.add_error(f"字段 '{field_name}' 长度 {length} 大于最大长度 {max_len}")

        choices = schema.get("choices")
        if choices is not None and value not in choices:
            result.add_error(f"字段 '{field_name}' 的值 '{value}' 不在允许的选项中: {choices}")

        pattern = schema.get("pattern")
        if pattern and isinstance(value, str) and not re.match(pattern, value):
            result.add_error(f"字段 '{field_name}' 的值 '{value}' 不匹配模式: {pattern}")

        custom_validator = schema.get("custom")
        if custom_validator and callable(custom_validator):
            try:
                custom_result = custom_validator(value)
                if isinstance(custom_result, bool) and not custom_result:
                    result.add_error(f"字段 '{field_name}' 自定义验证失败")
                elif isinstance(custom_result, str):
                    result.add_error(f"字段 '{field_name}': {custom_result}")
                elif isinstance(custom_result, ValidationResult):
                    result.merge(custom_result)
            except Exception as e:
                result.add_error(f"字段 '{field_name}' 自定义验证异常: {str(e)}")

        return result

    def validate_user_input(
        self,
        data: dict[str, Any],
    ) -> ValidationResult:
        """
        验证用户输入数据

        Args:
            data: 用户输入数据字典

        Returns:
            ValidationResult: 验证结果
        """
        result = ValidationResult(valid=True)

        if not isinstance(data, dict):
            result.add_error("输入数据必须是字典类型")
            return result

        for key, value in data.items():
            if not isinstance(key, str):
                result.add_error(f"键必须是字符串类型: {key}")
                continue

            if not key.strip():
                result.add_error("键不能为空字符串")
                continue

            if len(key) > 100:
                result.add_warning(f"键过长: {key[:50]}...")

            if isinstance(value, str):
                if len(value) > self.max_string_length:
                    result.add_error(
                        f"字符串值过长 (键: {key}): {len(value)} > {self.max_string_length}"
                    )

                dangerous_chars = ["<", ">", '"', "'", "&", "\x00"]
                for char in dangerous_chars:
                    if char in value:
                        result.add_warning(f"字符串包含潜在危险字符 (键: {key}): {repr(char)}")

                sql_patterns = [
                    r"(?i)\bSELECT\b.*\bFROM\b",
                    r"(?i)\bINSERT\b.*\bINTO\b",
                    r"(?i)\bUPDATE\b.*\bSET\b",
                    r"(?i)\bDELETE\b.*\bFROM\b",
                    r"(?i)\bDROP\b.*\bTABLE\b",
                    r"(?i)\bUNION\b.*\bSELECT\b",
                    r"(?i)\bOR\b.*=\b",
                    r"(?i)\bAND\b.*=\b",
                    r"--",
                    r"/\*",
                    r"\*/",
                ]
                for pattern in sql_patterns:
                    if re.search(pattern, value):
                        result.add_warning(f"检测到潜在 SQL 注入模式 (键: {key})")
                        break

                xss_patterns = [
                    r"(?i)<script",
                    r"(?i)javascript:",
                    r"(?i)on\w+\s*=",
                    r"(?i)<iframe",
                    r"(?i)<object",
                    r"(?i)<embed",
                ]
                for pattern in xss_patterns:
                    if re.search(pattern, value):
                        result.add_warning(f"检测到潜在 XSS 攻击模式 (键: {key})")
                        break

        return result

    def add_dangerous_pattern(self, pattern: str) -> None:
        """添加自定义危险模式"""
        self._dangerous_patterns.append(pattern)
        self._compiled_patterns.append(re.compile(pattern))

    def remove_dangerous_pattern(self, pattern: str) -> bool:
        """移除危险模式"""
        if pattern in self._dangerous_patterns:
            index = self._dangerous_patterns.index(pattern)
            self._dangerous_patterns.pop(index)
            self._compiled_patterns.pop(index)
            return True
        return False


__all__ = ["ValidationResult", "InputValidator"]

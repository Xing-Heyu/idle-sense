"""
沙箱安全模块

提供代码安全验证和安全策略管理
"""

import ast
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SecurityLevel(Enum):
    """安全级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityPolicy:
    """安全策略配置"""
    allowed_modules: set[str] = field(default_factory=lambda: {
        'math', 'random', 'statistics', 'time', 'datetime',
        'collections', 'itertools', 'functools', 'operator',
        'json', 're', 'string', 'hashlib', 'base64',
        'decimal', 'fractions', 'numbers', 'copy',
        'typing', 'dataclasses', 'enum',
    })

    dangerous_builtins: set[str] = field(default_factory=lambda: {
        'eval', 'exec', 'compile', 'input', 'open', 'file',
        '__import__', 'reload', 'globals', 'locals', 'vars',
        'dir', 'help', 'exit', 'quit', 'license', 'credits',
        'breakpoint', 'memoryview',
    })

    dangerous_attributes: set[str] = field(default_factory=lambda: {
        '__class__', '__base__', '__bases__', '__subclasses__',
        '__mro__', '__init__', '__new__', '__del__',
        '__getattribute__', '__setattr__', '__delattr__',
        '__dict__', '__globals__', '__code__', '__builtins__',
    })

    max_code_length: int = 100000
    max_loop_iterations: int = 10000000
    allow_network: bool = False
    allow_file_access: bool = False
    allow_subprocess: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_modules": list(self.allowed_modules),
            "dangerous_builtins": list(self.dangerous_builtins),
            "dangerous_attributes": list(self.dangerous_attributes),
            "max_code_length": self.max_code_length,
            "max_loop_iterations": self.max_loop_iterations,
            "allow_network": self.allow_network,
            "allow_file_access": self.allow_file_access,
            "allow_subprocess": self.allow_subprocess,
        }


@dataclass
class ValidationResult:
    """验证结果"""
    is_safe: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    security_level: SecurityLevel = SecurityLevel.MEDIUM

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "errors": self.errors,
            "warnings": self.warnings,
            "security_level": self.security_level.value,
        }


class CodeValidator:
    """代码安全验证器"""

    def __init__(self, policy: Optional[SecurityPolicy] = None):
        self.policy = policy or SecurityPolicy()

    def validate(self, code: str) -> ValidationResult:
        """验证代码安全性"""
        errors = []
        warnings = []

        if len(code) > self.policy.max_code_length:
            errors.append(f"代码长度超过限制: {len(code)} > {self.policy.max_code_length}")
            return ValidationResult(
                is_safe=False,
                errors=errors,
                security_level=SecurityLevel.CRITICAL
            )

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            errors.append(f"语法错误: {e}")
            return ValidationResult(
                is_safe=False,
                errors=errors,
                security_level=SecurityLevel.CRITICAL
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    if module_name not in self.policy.allowed_modules:
                        errors.append(f"禁止导入模块: {module_name}")

            elif isinstance(node, ast.ImportFrom):
                module_name = node.module.split('.')[0] if node.module else ''
                if module_name not in self.policy.allowed_modules:
                    errors.append(f"禁止从模块导入: {module_name}")

            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name in self.policy.dangerous_builtins:
                        errors.append(f"禁止调用危险函数: {func_name}")

            elif isinstance(node, ast.Attribute):
                attr_name = node.attr
                if attr_name in self.policy.dangerous_attributes:
                    errors.append(f"禁止访问危险属性: {attr_name}")
                elif attr_name.startswith('_') and not attr_name.startswith('__'):
                    warnings.append(f"访问私有属性: {attr_name}")

        security_level = SecurityLevel.LOW
        if errors:
            security_level = SecurityLevel.CRITICAL
        elif warnings:
            security_level = SecurityLevel.MEDIUM

        return ValidationResult(
            is_safe=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            security_level=security_level
        )

    def check_code_safety(self, code: str) -> dict[str, Any]:
        """兼容旧接口的安全检查"""
        result = self.validate(code)
        return {
            'safe': result.is_safe,
            'error': '; '.join(result.errors) if result.errors else None,
            'warnings': result.warnings,
            'security_level': result.security_level.value,
        }


__all__ = ["SecurityLevel", "SecurityPolicy", "ValidationResult", "CodeValidator"]

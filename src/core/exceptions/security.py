"""
安全相关异常类模块
"""

from typing import Any, Optional

from src.core.exceptions.base import IdleSenseError


class SecurityError(IdleSenseError):
    """
    安全相关错误基类
    """

    def __init__(
        self,
        message: str,
        code: str = "SECURITY_ERROR",
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, code, details)


class ValidationError(SecurityError):
    """
    验证错误
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        details = details or {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)[:100]
        super().__init__(message, "VALIDATION_ERROR", details)


class PermissionDeniedError(SecurityError):
    """
    权限拒绝错误
    """

    def __init__(
        self,
        user_id: str,
        permission: str,
        resource: Optional[str] = None,
        message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        message = message or f"用户 {user_id} 没有权限执行 {permission}"
        details = details or {}
        details["user_id"] = user_id
        details["permission"] = permission
        if resource:
            details["resource"] = resource
        super().__init__(message, "PERMISSION_DENIED", details)


__all__ = ["SecurityError", "ValidationError", "PermissionDeniedError"]

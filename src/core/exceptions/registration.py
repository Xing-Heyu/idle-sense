"""
注册相关异常类模块

提供用户注册流程中的专用异常类
"""

from typing import Any, Optional

from src.core.exceptions.base import IdleSenseError


class RegistrationError(IdleSenseError):
    """
    注册错误基类

    所有注册相关异常的基类
    """

    def __init__(
        self,
        message: str,
        code: str = "REGISTRATION_ERROR",
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, code, details)


class UsernameValidationError(RegistrationError):
    """
    用户名验证错误

    当用户名不符合验证规则时抛出
    """

    def __init__(
        self,
        message: str,
        username: Optional[str] = None,
        field: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        details = details or {}
        if username is not None:
            details["username"] = username
        if field is not None:
            details["field"] = field
        super().__init__(message, "USERNAME_VALIDATION_ERROR", details)


class StorageError(RegistrationError):
    """
    存储错误

    当无法存储用户数据时抛出（磁盘空间不足、路径问题等）
    """

    def __init__(
        self,
        message: str,
        path: Optional[str] = None,
        original_error: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        details = details or {}
        if path is not None:
            details["path"] = path
        if original_error is not None:
            details["original_error"] = original_error
        super().__init__(message, "STORAGE_ERROR", details)


class RegistrationPermissionError(RegistrationError):
    """
    注册权限错误

    当没有权限执行注册操作时抛出
    """

    def __init__(
        self,
        message: str,
        path: Optional[str] = None,
        required_permission: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        details = details or {}
        if path is not None:
            details["path"] = path
        if required_permission is not None:
            details["required_permission"] = required_permission
        super().__init__(message, "REGISTRATION_PERMISSION_ERROR", details)


class UserDataConflictError(RegistrationError):
    """
    用户数据冲突错误

    当用户ID冲突或数据损坏时抛出
    """

    def __init__(
        self,
        message: str,
        user_id: Optional[str] = None,
        conflict_type: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        details = details or {}
        if user_id is not None:
            details["user_id"] = user_id
        if conflict_type is not None:
            details["conflict_type"] = conflict_type
        super().__init__(message, "USER_DATA_CONFLICT_ERROR", details)


__all__ = [
    "RegistrationError",
    "UsernameValidationError",
    "StorageError",
    "RegistrationPermissionError",
    "UserDataConflictError",
]

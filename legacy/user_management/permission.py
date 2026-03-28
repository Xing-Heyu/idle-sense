"""
permission.py
权限验证模块 - 确保用户只能操作自己的资源
"""

from functools import wraps
from typing import Any, Callable, Optional

from .auth import AuthManager


class PermissionDeniedError(Exception):
    """权限拒绝异常"""
    def __init__(self, message: str = "无权操作此资源"):
        self.message = message
        super().__init__(self.message)


class PermissionValidator:
    """权限验证器"""

    def __init__(self, auth_manager: AuthManager):
        self.auth_manager = auth_manager

    def validate_session(self, session_id: str) -> str:
        """验证会话并返回用户ID"""
        user_id = self.auth_manager.validate_session(session_id)
        if not user_id:
            raise PermissionDeniedError("无效会话，请重新登录")
        return user_id

    def validate_user_active(self, user_id: str) -> None:
        """验证用户是否活跃"""
        user = self.auth_manager.get_user_by_id(user_id)
        if not user:
            raise PermissionDeniedError("用户不存在")
        if not user.is_active:
            raise PermissionDeniedError("账户已被禁用")

    def validate_resource_ownership(self, session_id: str, resource_user_id: str) -> str:
        """验证资源所有权"""
        user_id = self.validate_session(session_id)
        self.validate_user_active(user_id)

        if user_id != resource_user_id:
            raise PermissionDeniedError("无权操作他人资源")

        return user_id

    def validate_task_ownership(self, session_id: str, task_user_id: str) -> str:
        """验证任务所有权"""
        return self.validate_resource_ownership(session_id, task_user_id)

    def validate_file_ownership(self, session_id: str, file_user_id: str) -> str:
        """验证文件所有权"""
        return self.validate_resource_ownership(session_id, file_user_id)


def require_permission(get_resource_user_id: Callable[..., str]):
    """
    权限验证装饰器
    
    用法:
        @require_permission(lambda args, kwargs: kwargs.get('user_id'))
        def delete_task(task_id: str, user_id: str):
            ...
    
    Args:
        get_resource_user_id: 从函数参数中获取资源所属用户ID的函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            session_id = kwargs.get('session_id')
            if not session_id:
                raise PermissionDeniedError("缺少会话信息")

            resource_user_id = get_resource_user_id(args, kwargs)

            from . import get_permission_validator
            validator = get_permission_validator()

            validator.validate_resource_ownership(session_id, resource_user_id)

            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_session(func: Callable) -> Callable:
    """
    会话验证装饰器 - 仅验证会话有效性，不验证资源所有权
    
    用法:
        @require_session
        def get_my_tasks(session_id: str):
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        session_id = kwargs.get('session_id')
        if not session_id:
            raise PermissionDeniedError("缺少会话信息")

        from . import get_permission_validator
        validator = get_permission_validator()

        user_id = validator.validate_session(session_id)
        validator.validate_user_active(user_id)

        kwargs['_validated_user_id'] = user_id

        return func(*args, **kwargs)
    return wrapper


_permission_validator: Optional[PermissionValidator] = None


def init_permission_validator(auth_manager: AuthManager) -> PermissionValidator:
    """初始化权限验证器"""
    global _permission_validator
    _permission_validator = PermissionValidator(auth_manager)
    return _permission_validator


def get_permission_validator() -> PermissionValidator:
    """获取权限验证器实例"""
    if _permission_validator is None:
        raise RuntimeError("权限验证器未初始化，请先调用 init_permission_validator()")
    return _permission_validator

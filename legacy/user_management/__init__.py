# 用户管理模块

from .auth import AuthManager
from .local_authorization import LocalOperationAuthorization, authorization_manager
from .models import User, UserQuota, hash_password, verify_password
from .permission import (
    PermissionDeniedError,
    PermissionValidator,
    get_permission_validator,
    init_permission_validator,
    require_permission,
    require_session,
)
from .quota import QuotaManager

_auth_manager: AuthManager | None = None
_quota_manager: QuotaManager | None = None


def get_auth_manager() -> AuthManager:
    """获取认证管理器单例"""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


def get_quota_manager() -> QuotaManager:
    """获取配额管理器单例"""
    global _quota_manager
    if _quota_manager is None:
        _quota_manager = QuotaManager()
    return _quota_manager


def init_user_management() -> tuple[AuthManager, QuotaManager, PermissionValidator]:
    """初始化用户管理模块"""
    auth_manager = get_auth_manager()
    quota_manager = get_quota_manager()
    permission_validator = init_permission_validator(auth_manager)
    return auth_manager, quota_manager, permission_validator


__all__ = [
    "User",
    "UserQuota",
    "hash_password",
    "verify_password",
    "AuthManager",
    "QuotaManager",
    "LocalOperationAuthorization",
    "authorization_manager",
    "PermissionValidator",
    "PermissionDeniedError",
    "require_permission",
    "require_session",
    "init_permission_validator",
    "get_permission_validator",
    "get_auth_manager",
    "get_quota_manager",
    "init_user_management",
]

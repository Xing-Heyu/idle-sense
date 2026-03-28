"""
安全模块

提供权限、角色等安全相关功能
"""

from src.core.security.permission import (
    ROLES,
    Permission,
    PermissionService,
    Role,
    require_permission,
)

__all__ = [
    "Permission",
    "Role",
    "ROLES",
    "PermissionService",
    "require_permission",
]

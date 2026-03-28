"""
RBAC 权限模型

提供基于角色的访问控制功能
"""

from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Set


class Permission(Enum):
    """权限枚举"""

    TASK_CREATE = "task:create"
    TASK_READ = "task:read"
    TASK_UPDATE = "task:update"
    TASK_DELETE = "task:delete"

    NODE_MANAGE = "node:manage"
    NODE_READ = "node:read"

    USER_MANAGE = "user:manage"
    USER_READ = "user:read"

    SYSTEM_CONFIG = "system:config"
    SYSTEM_VIEW = "system:view"

    AUDIT_READ = "audit:read"


@dataclass
class Role:
    """角色定义"""

    name: str
    permissions: Set[Permission] = field(default_factory=set)
    description: str = ""

    def has_permission(self, permission: Permission) -> bool:
        """检查角色是否拥有指定权限"""
        return permission in self.permissions

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "permissions": [p.value for p in self.permissions],
            "description": self.description,
        }


ROLES: dict[str, Role] = {
    "admin": Role(
        name="admin",
        permissions={
            Permission.TASK_CREATE,
            Permission.TASK_READ,
            Permission.TASK_UPDATE,
            Permission.TASK_DELETE,
            Permission.NODE_MANAGE,
            Permission.NODE_READ,
            Permission.USER_MANAGE,
            Permission.USER_READ,
            Permission.SYSTEM_CONFIG,
            Permission.SYSTEM_VIEW,
            Permission.AUDIT_READ,
        },
        description="系统管理员，拥有所有权限",
    ),
    "user": Role(
        name="user",
        permissions={
            Permission.TASK_CREATE,
            Permission.TASK_READ,
            Permission.TASK_UPDATE,
            Permission.TASK_DELETE,
            Permission.NODE_READ,
            Permission.USER_READ,
            Permission.SYSTEM_VIEW,
        },
        description="普通用户，可以管理自己的任务",
    ),
    "guest": Role(
        name="guest",
        permissions={
            Permission.TASK_READ,
            Permission.NODE_READ,
            Permission.SYSTEM_VIEW,
        },
        description="访客，只能查看信息",
    ),
    "node_operator": Role(
        name="node_operator",
        permissions={
            Permission.TASK_READ,
            Permission.NODE_MANAGE,
            Permission.NODE_READ,
            Permission.SYSTEM_VIEW,
        },
        description="节点操作员，可以管理节点",
    ),
}


class PermissionService:
    """
    权限服务

    实现基于角色的访问控制
    """

    def __init__(self):
        self.user_roles: dict[str, Set[str]] = {}
        self._lock = None

    def assign_role(self, user_id: str, role_name: str) -> bool:
        """为用户分配角色"""
        if role_name not in ROLES:
            return False

        if user_id not in self.user_roles:
            self.user_roles[user_id] = set()

        self.user_roles[user_id].add(role_name)
        return True

    def remove_role(self, user_id: str, role_name: str) -> bool:
        """移除用户角色"""
        if user_id in self.user_roles and role_name in self.user_roles[user_id]:
            self.user_roles[user_id].remove(role_name)
            return True
        return False

    def check_permission(self, user_id: str, permission: Permission) -> bool:
        """检查用户是否拥有指定权限"""
        user_roles = self.user_roles.get(user_id, set())

        for role_name in user_roles:
            role = ROLES.get(role_name)
            if role and permission in role.permissions:
                return True

        return False

    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """获取用户所有权限"""
        user_roles = self.user_roles.get(user_id, set())
        permissions: Set[Permission] = set()

        for role_name in user_roles:
            role = ROLES.get(role_name)
            if role:
                permissions.update(role.permissions)

        return permissions

    def get_user_roles(self, user_id: str) -> list[str]:
        """获取用户角色列表"""
        return list(self.user_roles.get(user_id, set()))

    def has_role(self, user_id: str, role_name: str) -> bool:
        """检查用户是否拥有指定角色"""
        return role_name in self.user_roles.get(user_id, set())


def require_permission(permission: Permission) -> Callable:
    """
    权限检查装饰器

    用法:
        @require_permission(Permission.TASK_CREATE)
        def create_task(...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = kwargs.get("user_id")
            if user_id is None and args:
                for arg in args:
                    if hasattr(arg, "user_id"):
                        user_id = arg.user_id
                        break

            if user_id is None:
                from src.core.exceptions import PermissionDeniedError

                raise PermissionDeniedError(
                    user_id="unknown",
                    permission=permission.value,
                    message="无法确定用户身份",
                )

            service = PermissionService()
            if not service.check_permission(user_id, permission):
                from src.core.exceptions import PermissionDeniedError

                raise PermissionDeniedError(
                    user_id=user_id,
                    permission=permission.value,
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "Permission",
    "Role",
    "ROLES",
    "PermissionService",
    "require_permission",
]

import secrets
from typing import Any, Optional

from .models import User, UserQuota


class AuthManager:
    """认证管理器 - 支持密码认证和权限验证"""
    def __init__(self):
        self.users: dict[str, User] = {}
        self.users_by_username: dict[str, str] = {}
        self.user_quotas: dict[str, UserQuota] = {}
        self.sessions: dict[str, str] = {}

    def register_user(self, username: str, email: str, password: str,
                      agree_folder_usage: bool = False,
                      quota_config: dict | None = None) -> dict[str, Any]:
        """注册新用户（需要密码）"""
        if username in self.users_by_username:
            return {"success": False, "error": "用户名已存在"}

        if any(u.email == email for u in self.users.values()):
            return {"success": False, "error": "邮箱已存在"}

        if not password or len(password) < 6:
            return {"success": False, "error": "密码长度至少6位"}

        user = User(username, email, password)

        if quota_config:
            quota = UserQuota(
                user.user_id,
                daily_tasks_limit=quota_config.get('daily_tasks_limit'),
                concurrent_tasks_limit=quota_config.get('concurrent_tasks_limit'),
                cpu_quota=quota_config.get('cpu_quota'),
                memory_quota=quota_config.get('memory_quota')
            )
        else:
            quota = UserQuota(user.user_id)

        if agree_folder_usage:
            user.agree_folder_usage()

        self.users[user.user_id] = user
        self.users_by_username[username] = user.user_id
        self.user_quotas[user.user_id] = quota

        return {
            "success": True,
            "user_id": user.user_id,
            "user": user.to_dict(),
            "quota": quota.to_dict(),
            "folder_agreement": agree_folder_usage
        }

    def login(self, username: str, password: str) -> dict[str, Any]:
        """用户登录（验证密码）"""
        if username not in self.users_by_username:
            return {"success": False, "error": "用户名或密码错误"}

        user_id = self.users_by_username[username]
        user = self.users.get(user_id)

        if not user:
            return {"success": False, "error": "用户不存在"}

        if not user.is_active:
            return {"success": False, "error": "账户已被禁用"}

        if not user.verify_password(password):
            return {"success": False, "error": "用户名或密码错误"}

        session_id = self.create_session(user.user_id)
        quota = self.user_quotas.get(user.user_id)

        return {
            "success": True,
            "session_id": session_id,
            "user_id": user.user_id,
            "user": user.to_dict(),
            "quota": quota.to_dict() if quota else None
        }

    def logout(self, session_id: str) -> bool:
        """用户登出"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        return self.users.get(user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        if username in self.users_by_username:
            return self.users.get(self.users_by_username[username])
        return None

    def get_quota_by_user_id(self, user_id: str) -> Optional[UserQuota]:
        """获取用户配额"""
        return self.user_quotas.get(user_id)

    def create_session(self, user_id: str) -> str:
        """创建会话"""
        session_id = secrets.token_urlsafe(32)
        self.sessions[session_id] = user_id
        return session_id

    def validate_session(self, session_id: str) -> Optional[str]:
        """验证会话，返回用户ID"""
        return self.sessions.get(session_id)

    def get_user_by_session(self, session_id: str) -> Optional[User]:
        """通过会话ID获取用户"""
        user_id = self.sessions.get(session_id)
        if user_id:
            return self.users.get(user_id)
        return None

    def change_password(self, user_id: str, old_password: str, new_password: str) -> dict[str, Any]:
        """修改密码"""
        user = self.users.get(user_id)
        if not user:
            return {"success": False, "error": "用户不存在"}

        if not user.verify_password(old_password):
            return {"success": False, "error": "原密码错误"}

        if len(new_password) < 6:
            return {"success": False, "error": "新密码长度至少6位"}

        user.set_password(new_password)
        return {"success": True, "message": "密码修改成功"}

    def verify_permission(self, session_id: str, resource_user_id: str) -> dict[str, Any]:
        """验证用户是否有权限操作指定资源"""
        user_id = self.sessions.get(session_id)
        if not user_id:
            return {"allowed": False, "error": "无效会话"}

        if user_id != resource_user_id:
            return {"allowed": False, "error": "无权操作他人资源"}

        user = self.users.get(user_id)
        if not user or not user.is_active:
            return {"allowed": False, "error": "用户不存在或已禁用"}

        return {"allowed": True, "user_id": user_id}

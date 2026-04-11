import os
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any, Optional

from .models import User, UserQuota


@dataclass
class SessionInfo:
    """会话信息"""

    user_id: str
    created_at: float
    expires_at: float
    ip_address: Optional[str] = None


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    验证密码强度

    要求:
    - 至少8个字符
    - 包含至少一个大写字母
    - 包含至少一个小写字母
    - 包含至少一个数字

    Returns:
        (是否有效, 错误信息)
    """
    if not password:
        return False, "密码不能为空"

    if len(password) < 8:
        return False, "密码长度至少8位"

    if len(password) > 128:
        return False, "密码长度不能超过128位"

    if not re.search(r'[A-Z]', password):
        return False, "密码必须包含至少一个大写字母"

    if not re.search(r'[a-z]', password):
        return False, "密码必须包含至少一个小写字母"

    if not re.search(r'\d', password):
        return False, "密码必须包含至少一个数字"

    common_passwords = {
        'password', 'Password1', 'Password123', 'Admin123',
        'Qwerty123', 'Letmein1', 'Welcome1', 'Passw0rd'
    }
    if password in common_passwords:
        return False, "密码过于简单，请使用更复杂的密码"

    return True, ""


DEFAULT_SESSION_TIMEOUT = int(os.getenv("AUTH_SESSION_TIMEOUT", "3600"))


class AuthManager:
    """认证管理器 - 支持密码认证和权限验证"""

    def __init__(self, session_timeout: int = DEFAULT_SESSION_TIMEOUT):
        self.session_timeout = max(300, min(session_timeout, 86400))
        self.users: dict[str, User] = {}
        self.users_by_username: dict[str, str] = {}
        self.user_quotas: dict[str, UserQuota] = {}
        self.sessions: dict[str, SessionInfo] = {}

    def register_user(
        self,
        username: str,
        email: str,
        password: str,
        agree_folder_usage: bool = False,
        quota_config: dict | None = None,
    ) -> dict[str, Any]:
        """注册新用户（需要密码）"""
        if username in self.users_by_username:
            return {"success": False, "error": "用户名已存在"}

        if any(u.email == email for u in self.users.values()):
            return {"success": False, "error": "邮箱已存在"}

        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            return {"success": False, "error": error_msg}

        user = User(username, email, password)

        if quota_config:
            quota = UserQuota(
                user.user_id,
                daily_tasks_limit=quota_config.get("daily_tasks_limit"),
                concurrent_tasks_limit=quota_config.get("concurrent_tasks_limit"),
                cpu_quota=quota_config.get("cpu_quota"),
                memory_quota=quota_config.get("memory_quota"),
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
            "folder_agreement": agree_folder_usage,
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
            "quota": quota.to_dict() if quota else None,
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

    def create_session(self, user_id: str, ip_address: Optional[str] = None) -> str:
        """创建会话

        Args:
            user_id: 用户ID
            ip_address: 客户端IP地址（可选）

        Returns:
            session_id: 会话ID
        """
        session_id = secrets.token_urlsafe(32)
        now = time.time()
        self.sessions[session_id] = SessionInfo(
            user_id=user_id,
            created_at=now,
            expires_at=now + self.session_timeout,
            ip_address=ip_address,
        )
        return session_id

    def validate_session(self, session_id: str, ip_address: Optional[str] = None) -> Optional[str]:
        """验证会话，返回用户ID

        Args:
            session_id: 会话ID
            ip_address: 客户端IP地址（可选，用于IP绑定验证）

        Returns:
            用户ID，如果会话无效则返回None
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        # 检查是否过期
        if time.time() > session.expires_at:
            del self.sessions[session_id]
            return None

        # 可选：IP绑定验证
        if ip_address and session.ip_address and session.ip_address != ip_address:
            return None

        return session.user_id

    def refresh_session(self, session_id: str) -> bool:
        """刷新会话过期时间"""
        session = self.sessions.get(session_id)
        if not session:
            return False
        session.expires_at = time.time() + self.session_timeout
        return True

    def cleanup_expired_sessions(self) -> int:
        """清理过期会话，返回清理数量"""
        now = time.time()
        expired = [sid for sid, s in self.sessions.items() if now > s.expires_at]
        for sid in expired:
            del self.sessions[sid]
        return len(expired)

    def get_user_by_session(
        self, session_id: str, ip_address: Optional[str] = None
    ) -> Optional[User]:
        """通过会话ID获取用户"""
        user_id = self.validate_session(session_id, ip_address)
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

        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            return {"success": False, "error": error_msg}

        user.set_password(new_password)
        return {"success": True, "message": "密码修改成功"}

    def verify_permission(
        self, session_id: str, resource_user_id: str, ip_address: Optional[str] = None
    ) -> dict[str, Any]:
        """验证用户是否有权限操作指定资源"""
        user_id = self.validate_session(session_id, ip_address)
        if not user_id:
            return {"allowed": False, "error": "无效会话或会话已过期"}

        if user_id != resource_user_id:
            return {"allowed": False, "error": "无权操作他人资源"}

        user = self.users.get(user_id)
        if not user or not user.is_active:
            return {"allowed": False, "error": "用户不存在或已禁用"}

        return {"allowed": True, "user_id": user_id}

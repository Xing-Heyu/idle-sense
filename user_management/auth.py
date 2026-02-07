import hashlib
import secrets
from typing import Optional, Dict, Any
from .models import User, UserQuota

class AuthManager:
    """认证管理器"""
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.user_quotas: Dict[str, UserQuota] = {}
        self.sessions: Dict[str, str] = {}  # session_id -> user_id
        
    def register_user(self, username: str, email: str) -> Dict[str, Any]:
        """注册新用户"""
        if any(u.username == username for u in self.users.values()):
            return {"success": False, "error": "用户名已存在"}
            
        if any(u.email == email for u in self.users.values()):
            return {"success": False, "error": "邮箱已存在"}
            
        user = User(username, email)
        quota = UserQuota(user.user_id)
        
        self.users[user.user_id] = user
        self.user_quotas[user.user_id] = quota
        
        return {
            "success": True, 
            "user_id": user.user_id,
            "user": user.to_dict(),
            "quota": quota.to_dict()
        }
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        return self.users.get(user_id)
    
    def get_quota_by_user_id(self, user_id: str) -> Optional[UserQuota]:
        """获取用户配额"""
        return self.user_quotas.get(user_id)
    
    def create_session(self, user_id: str) -> str:
        """创建会话"""
        session_id = secrets.token_urlsafe(32)
        self.sessions[session_id] = user_id
        return session_id
    
    def validate_session(self, session_id: str) -> Optional[str]:
        """验证会话"""
        return self.sessions.get(session_id)
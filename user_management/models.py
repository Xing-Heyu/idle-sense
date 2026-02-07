from datetime import datetime
from typing import Dict, Any, Optional
import uuid

class User:
    """用户模型"""
    def __init__(self, username: str, email: str):
        self.user_id = str(uuid.uuid4())
        self.username = username
        self.email = email
        self.created_at = datetime.now()
        self.is_active = True
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active
        }

class UserQuota:
    """用户资源配额 - 开源版本无限制"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.daily_tasks_limit = 0          # 0表示无限制
        self.concurrent_tasks_limit = 0    # 0表示无限制
        self.cpu_quota = 0.0               # 0表示无限制
        self.memory_quota = 0              # 0表示无限制
        self.daily_usage = 0               # 记录使用量（仅用于统计）
        self.current_tasks = 0             # 记录当前任务数（仅用于统计）
        
    def can_submit_task(self) -> bool:
        """开源版本始终允许提交任务"""
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "daily_tasks_limit": "无限制",
            "concurrent_tasks_limit": "无限制", 
            "cpu_quota": "无限制",
            "memory_quota": "无限制",
            "daily_usage": self.daily_usage,
            "current_tasks": self.current_tasks
        }
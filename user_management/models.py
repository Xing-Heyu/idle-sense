# c:\idle-sense\user_management\models.py
from datetime import
 datetime
from typing import Dict, Any,
 Optional
import
 uuid

class User:
    """用户模型"""
    def __init__(self, username: str, email: str):
        self.user_id = str(uuid.uuid4())
        self.username =
 username
        self.email =
 email
        self.created_at = datetime.now()
        self.is_active = True
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
            "is_active": self.
is_active
        }

class UserQuota:
    """用户资源配额"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.concurrent_tasks_limit = 5        # 并发任务数限制
        self.cpu_quota = 10.0                 # CPU配额（核心）
        self.memory_quota = 4096              # 内存配额（MB）
        self.daily_usage = 0                  # 今日已使用任务数
        self.current_tasks = 0                # 当前运行任务数
        
    def can_submit_task(self) -> bool:
        """检查是否可以提交新任务"""
        return (self.daily_usage < self.daily_tasks_limit and 
                self.current_tasks < self.concurrent_tasks_limit)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "daily_tasks_limit": self.daily_tasks_limit,
            "concurrent_tasks_limit": self.concurrent_tasks_limit,
            "cpu_quota": self.cpu_quota,
            "memory_quota": self.memory_quota,
            "daily_usage": self.daily_usage,
            "current_tasks": self.
current_tasks
        }

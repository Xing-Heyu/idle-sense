from datetime import datetime,
 timedelta
from typing import Dict,
 Optional
from .models import
 UserQuota

class QuotaManager:
    """配额管理器"""
    def __init__(self):
        self.quotas: Dict[str, UserQuota] = {}
        self.last_reset_date = datetime.now().date()
        
    def check_quota(self, user_id: str) -> Dict[str, Any]:
        """检查用户配额"""
        quota = self.quotas.get(user_id)
        if not quota:
            return {"allowed": False, "error": "用户不存在"}
            
        # 每日重置检查
        self._reset_daily_usage_if_needed(quota)
        
        if not quota.can_submit_task():
            return {
                "allowed": False,
                "error": "配额不足",
                "details": {
                    "daily_remaining": quota.daily_tasks_limit - quota.daily_usage,
                    "concurrent_remaining": quota.concurrent_tasks_limit - quota.
current_tasks
                }
            }
            
        return {"allowed": True, "quota": quota.to_dict()}
    
    def consume_quota(self, user_id: str) -> bool:
        """消耗配额"""
        quota = self.quotas.get(user_id)
        if not quota or not quota.can_submit_task():
            return False
            
        quota.daily_usage += 1
        quota.current_tasks += 1
        return True
    
    def release_quota(self, user_id: str):
        """释放配额（任务完成时调用）"""
        quota = self.quotas.get(user_id)
        if quota and quota.current_tasks > 0:
            quota.current_tasks -= 1
    
    def _reset_daily_usage_if_needed(self, quota: UserQuota):
        """如果需要则重置每日使用量"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            quota.daily_usage = 0
            self.last_reset_date =
 today

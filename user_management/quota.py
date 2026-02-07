from datetime import datetime, timedelta
from typing import Dict, Optional
from .models import UserQuota

class QuotaManager:
    """配额管理器 - 开源版本无限制"""
    def __init__(self):
        self.quotas: Dict[str, UserQuota] = {}
        self.last_reset_date = datetime.now().date()
        
    def check_quota(self, user_id: str) -> Dict[str, Any]:
        """开源版本始终允许提交任务"""
        quota = self.quotas.get(user_id)
        if not quota:
            # 如果用户不存在，创建一个默认配额
            quota = UserQuota(user_id)
            self.quotas[user_id] = quota
            
        return {"allowed": True, "quota": quota.to_dict()}
    
    def consume_quota(self, user_id: str) -> bool:
        """记录任务提交（开源版本始终允许）"""
        quota = self.quotas.get(user_id)
        if not quota:
            # 如果用户不存在，创建一个默认配额
            quota = UserQuota(user_id)
            self.quotas[user_id] = quota
            
        # 仅用于统计，不影响任务提交
        quota.daily_usage += 1
        quota.current_tasks += 1
        return True
    
    def release_quota(self, user_id: str):
        """释放配额（任务完成时调用）"""
        quota = self.quotas.get(user_id)
        if quota and quota.current_tasks > 0:
            quota.current_tasks -= 1
    
    def _reset_daily_usage_if_needed(self, quota: UserQuota):
        """如果需要则重置每日使用量（仅用于统计）"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            quota.daily_usage = 0
            self.last_reset_date = today
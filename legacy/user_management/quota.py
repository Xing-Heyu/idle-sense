from datetime import datetime
from typing import Any

from .models import UserQuota


class QuotaManager:
    """配额管理器 - 支持强制限制"""

    def __init__(self):
        self.quotas: dict[str, UserQuota] = {}
        self.last_reset_date = datetime.now().date()

    def check_quota(self, user_id: str) -> dict[str, Any]:
        """检查用户配额"""
        quota = self.quotas.get(user_id)
        if not quota:
            quota = UserQuota(user_id)
            self.quotas[user_id] = quota

        allowed = quota.can_submit_task()
        result = {"allowed": allowed, "quota": quota.to_dict()}

        if not allowed:
            result["reason"] = quota.get_rejection_reason()

        return result

    def consume_quota(self, user_id: str) -> bool:
        """消耗配额（提交任务时调用）"""
        quota = self.quotas.get(user_id)
        if not quota:
            quota = UserQuota(user_id)
            self.quotas[user_id] = quota

        if not quota.can_submit_task():
            return False

        quota.daily_usage += 1
        quota.current_tasks += 1
        return True

    def release_quota(self, user_id: str):
        """释放配额（任务完成时调用）"""
        quota = self.quotas.get(user_id)
        if quota and quota.current_tasks > 0:
            quota.current_tasks -= 1

    def set_user_quota(
        self,
        user_id: str,
        daily_tasks_limit: int | None = None,
        concurrent_tasks_limit: int | None = None,
        cpu_quota: float | None = None,
        memory_quota: int | None = None,
    ) -> UserQuota:
        """设置用户配额"""
        quota = self.quotas.get(user_id)
        if not quota:
            quota = UserQuota(user_id)
            self.quotas[user_id] = quota

        if daily_tasks_limit is not None:
            quota.daily_tasks_limit = daily_tasks_limit
        if concurrent_tasks_limit is not None:
            quota.concurrent_tasks_limit = concurrent_tasks_limit
        if cpu_quota is not None:
            quota.cpu_quota = cpu_quota
        if memory_quota is not None:
            quota.memory_quota = memory_quota

        return quota

    def get_user_quota(self, user_id: str) -> UserQuota:
        """获取用户配额"""
        quota = self.quotas.get(user_id)
        if not quota:
            quota = UserQuota(user_id)
            self.quotas[user_id] = quota
        return quota

    def reset_daily_usage(self, user_id: str | None = None):
        """重置每日使用量"""
        if user_id:
            quota = self.quotas.get(user_id)
            if quota:
                quota.daily_usage = 0
                quota.last_reset_date = datetime.now().date()
        else:
            for quota in self.quotas.values():
                quota.daily_usage = 0
                quota.last_reset_date = datetime.now().date()
            self.last_reset_date = datetime.now().date()

    def get_usage_stats(self, user_id: str) -> dict[str, Any]:
        """获取用户使用统计"""
        quota = self.quotas.get(user_id)
        if not quota:
            return {"error": "用户不存在"}

        return {
            "user_id": user_id,
            "daily_usage": quota.daily_usage,
            "daily_limit": quota.daily_tasks_limit,
            "daily_remaining": (
                max(0, quota.daily_tasks_limit - quota.daily_usage)
                if quota.daily_tasks_limit > 0
                else "无限制"
            ),
            "current_tasks": quota.current_tasks,
            "concurrent_limit": quota.concurrent_tasks_limit,
            "concurrent_remaining": (
                max(0, quota.concurrent_tasks_limit - quota.current_tasks)
                if quota.concurrent_tasks_limit > 0
                else "无限制"
            ),
        }

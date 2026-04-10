import hashlib
import os
import secrets
import uuid
from datetime import datetime
from typing import Any


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, bytes]:
    """使用 PBKDF2 哈希密码"""
    if salt is None:
        salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return key.hex(), salt


def verify_password(password: str, stored_hash: str, salt: bytes) -> bool:
    """验证密码"""
    computed_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, stored_hash)


class User:
    """用户模型"""

    def __init__(self, username: str, email: str, password: str | None = None):
        self.user_id = str(uuid.uuid4())
        self.username = username
        self.email = email
        self.created_at = datetime.now()
        self.is_active = True
        self.folder_agreement = False
        self.user_folder_path = f"user_data (您的数据文件-主要工作区)/{self.user_id}"
        self.temp_folder_path = f"temp_data (临时文件-自动清理)/{self.user_id}"
        self.password_hash: str | None = None
        self.password_salt: bytes | None = None
        if password:
            self.set_password(password)

    def set_password(self, password: str):
        """设置密码"""
        self.password_hash, self.password_salt = hash_password(password)

    def verify_password(self, password: str) -> bool:
        """验证密码"""
        if not self.password_hash or not self.password_salt:
            return False
        return verify_password(password, self.password_hash, self.password_salt)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
            "folder_agreement": self.folder_agreement,
            "user_folder_path": self.user_folder_path,
            "temp_folder_path": self.temp_folder_path,
            "has_password": self.password_hash is not None,
        }

    def agree_folder_usage(self):
        """用户同意文件夹使用规则"""
        self.folder_agreement = True
        # 注意：文件夹创建应该在节点客户端进行，这里只记录同意状态
        return True


class UserQuota:
    """用户资源配额 - 支持强制限制"""

    DEFAULT_DAILY_LIMIT = 100
    DEFAULT_CONCURRENT_LIMIT = 5
    DEFAULT_CPU_QUOTA = 4.0
    DEFAULT_MEMORY_QUOTA = 4096

    _enforce_limits = True

    @classmethod
    def set_enforce_limits(cls, enforce: bool):
        """设置是否强制执行配额限制（全局配置）"""
        cls._enforce_limits = enforce

    @classmethod
    def get_enforce_limits(cls) -> bool:
        """获取当前配额限制模式"""
        return cls._enforce_limits

    def __init__(
        self,
        user_id: str,
        daily_tasks_limit: int | None = None,
        concurrent_tasks_limit: int | None = None,
        cpu_quota: float | None = None,
        memory_quota: int | None = None,
    ):
        self.user_id = user_id
        self.daily_tasks_limit = (
            daily_tasks_limit if daily_tasks_limit is not None else self.DEFAULT_DAILY_LIMIT
        )
        self.concurrent_tasks_limit = (
            concurrent_tasks_limit
            if concurrent_tasks_limit is not None
            else self.DEFAULT_CONCURRENT_LIMIT
        )
        self.cpu_quota = cpu_quota if cpu_quota is not None else self.DEFAULT_CPU_QUOTA
        self.memory_quota = memory_quota if memory_quota is not None else self.DEFAULT_MEMORY_QUOTA
        self.daily_usage = 0
        self.current_tasks = 0
        self.last_reset_date = datetime.now().date()

    def can_submit_task(self) -> bool:
        """检查是否可以提交任务"""
        if not self._enforce_limits:
            return True
        self._reset_daily_if_needed()
        if self.daily_tasks_limit > 0 and self.daily_usage >= self.daily_tasks_limit:
            return False
        return not (
            self.concurrent_tasks_limit > 0 and self.current_tasks >= self.concurrent_tasks_limit
        )

    def get_rejection_reason(self) -> str | None:
        """获取拒绝原因"""
        if not self._enforce_limits:
            return None
        self._reset_daily_if_needed()
        if self.daily_tasks_limit > 0 and self.daily_usage >= self.daily_tasks_limit:
            return f"已达到每日任务上限 ({self.daily_tasks_limit})"
        if self.concurrent_tasks_limit > 0 and self.current_tasks >= self.concurrent_tasks_limit:
            return f"已达到并发任务上限 ({self.concurrent_tasks_limit})"
        return None

    def _reset_daily_if_needed(self):
        """如果需要则重置每日使用量"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.daily_usage = 0
            self.last_reset_date = today

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "daily_tasks_limit": self.daily_tasks_limit if self.daily_tasks_limit > 0 else "无限制",
            "concurrent_tasks_limit": (
                self.concurrent_tasks_limit if self.concurrent_tasks_limit > 0 else "无限制"
            ),
            "cpu_quota": f"{self.cpu_quota}核" if self.cpu_quota > 0 else "无限制",
            "memory_quota": f"{self.memory_quota}MB" if self.memory_quota > 0 else "无限制",
            "daily_usage": self.daily_usage,
            "current_tasks": self.current_tasks,
            "enforce_limits": self._enforce_limits,
        }

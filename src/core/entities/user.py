"""
用户实体模块

基于DDD设计原则的用户实体：
- 唯一标识：user_id
- 属性：username, created_at, folder_location, last_login
- 方法：validate(), update_last_login(), is_authenticated

使用示例：
    from src.core.entities import User

    user = User(
        user_id="local_abc123",
        username="test_user",
        folder_location="project"
    )

    # 验证用户
    is_valid, message = user.validate()
"""

import hashlib
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """
    用户实体

    代表系统中的用户，具有以下职责：
    - 管理用户基本信息
    - 验证用户数据有效性
    - 记录用户登录状态
    """
    user_id: str
    username: str
    created_at: datetime = field(default_factory=datetime.now)
    folder_location: str = "project"
    last_login: Optional[datetime] = None

    @property
    def is_authenticated(self) -> bool:
        """检查用户是否已认证（曾登录过）"""
        return self.last_login is not None

    def validate(self) -> tuple[bool, str]:
        """
        验证用户实体有效性

        Returns:
            (是否有效, 错误消息)
        """
        if len(self.username) > 20:
            return False, "用户名长度不能超过20个字符"

        if not self.username:
            return False, "用户名不能为空"

        pattern = r'^[\u4e00-\u9fa5a-zA-Z0-9]+$'
        if not re.match(pattern, self.username):
            return False, "用户名只能包含中文、英文和数字"

        return True, "验证通过"

    def update_last_login(self) -> None:
        """更新最后登录时间"""
        self.last_login = datetime.now()

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "folder_location": self.folder_location,
            "last_login": self.last_login.isoformat() if self.last_login else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """从字典创建用户实体"""
        return cls(
            user_id=data.get("user_id", ""),
            username=data.get("username", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            folder_location=data.get("folder_location", "project"),
            last_login=datetime.fromisoformat(data["last_login"]) if data.get("last_login") else None
        )

    @staticmethod
    def generate_user_id(username: str) -> str:
        """生成用户ID"""
        return f"local_{hashlib.md5(f'{username}_{time.time()}'.encode()).hexdigest()[:8]}"


class UserFactory:
    """用户工厂类"""

    @staticmethod
    def create(username: str, folder_location: str = "project") -> User:
        """
        创建新用户

        Args:
            username: 用户名
            folder_location: 文件夹位置

        Returns:
            用户实体
        """
        user_id = User.generate_user_id(username)
        return User(
            user_id=user_id,
            username=username,
            folder_location=folder_location
        )

    @staticmethod
    def create_from_dict(data: dict) -> User:
        """从字典创建用户"""
        return User.from_dict(data)


__all__ = ["User", "UserFactory"]

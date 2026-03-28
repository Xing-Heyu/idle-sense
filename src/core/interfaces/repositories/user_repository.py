"""
用户仓储接口

定义用户数据访问的抽象接口：
- get_by_id: 根据ID获取用户
- get_by_username: 根据用户名获取用户
- save: 保存用户
- update: 更新用户
- list_all: 获取所有用户
- exists: 检查用户是否存在

使用示例：
    class FileUserRepository(IUserRepository):
        def get_by_id(self, user_id: str) -> Optional[User]:
            # 实现
            ...
"""

from abc import ABC, abstractmethod
from typing import Optional

from src.core.entities import User


class IUserRepository(ABC):
    """
    用户仓储接口

    定义用户数据访问的契约，具体实现由基础设施层完成
    """

    @abstractmethod
    def get_by_id(self, user_id: str) -> Optional[User]:
        """
        根据ID获取用户

        Args:
            user_id: 用户ID

        Returns:
            用户实体，如果不存在则返回None
        """
        pass

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[User]:
        """
        根据用户名获取用户

        Args:
            username: 用户名

        Returns:
            用户实体，如果不存在则返回None
        """
        pass

    @abstractmethod
    def save(self, user: User) -> User:
        """
        保存用户

        Args:
            user: 用户实体

        Returns:
            保存后的用户实体
        """
        pass

    @abstractmethod
    def update(self, user: User) -> User:
        """
        更新用户

        Args:
            user: 用户实体

        Returns:
            更新后的用户实体
        """
        pass

    @abstractmethod
    def delete(self, user_id: str) -> bool:
        """
        删除用户

        Args:
            user_id: 用户ID

        Returns:
            是否删除成功
        """
        pass

    @abstractmethod
    def list_all(self) -> list[User]:
        """
        获取所有用户

        Returns:
            用户实体列表
        """
        pass

    @abstractmethod
    def exists(self, username: str) -> bool:
        """
        检查用户名是否存在

        Args:
            username: 用户名

        Returns:
            是否存在
        """
        pass

    @abstractmethod
    def find_available_username(self, username: str) -> str:
        """
        查找可用的用户名

        如果用户名已存在，则生成一个新的可用用户名

        Args:
            username: 原始用户名

        Returns:
            可用的用户名
        """
        pass


__all__ = ["IUserRepository"]

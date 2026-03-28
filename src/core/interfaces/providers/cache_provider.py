"""
缓存提供者接口

定义缓存访问的抽象接口：
- get: 获取缓存值
- set: 设置缓存值
- delete: 删除缓存值
- clear: 清空缓存
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class ICacheProvider(ABC):
    """
    缓存提供者接口

    定义缓存访问的契约
    """

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或已过期则返回None
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None表示使用默认值
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        删除缓存值

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空缓存"""
        pass

    @abstractmethod
    def cleanup_expired(self) -> int:
        """
        清理过期条目

        Returns:
            清理的条目数
        """
        pass

    @abstractmethod
    def get_stats(self) -> dict:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        pass


__all__ = ["ICacheProvider"]

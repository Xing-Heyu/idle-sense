"""
配置提供者接口

定义配置访问的抽象接口：
- get: 获取配置值
- get_required: 获取必需配置值
- reload: 重新加载配置
"""

from abc import ABC, abstractmethod
from typing import Any


class IConfigProvider(ABC):
    """
    配置提供者接口

    定义配置访问的契约
    """

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值
        """
        pass

    @abstractmethod
    def get_required(self, key: str) -> Any:
        """
        获取必需的配置值

        Args:
            key: 配置键

        Returns:
            配置值

        Raises:
            ValueError: 配置值不存在
        """
        pass

    @abstractmethod
    def reload(self) -> None:
        """重新加载配置"""
        pass

    @abstractmethod
    def get_scheduler_url(self) -> str:
        """获取调度器URL"""
        pass

    @abstractmethod
    def get_api_timeout(self) -> int:
        """获取API超时时间"""
        pass

    @abstractmethod
    def get_refresh_interval(self) -> int:
        """获取刷新间隔"""
        pass


__all__ = ["IConfigProvider"]

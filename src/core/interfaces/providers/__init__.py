"""
providers - 提供者接口模块

定义基础设施接口：
- config_provider: 配置提供者
- cache_provider: 缓存提供者
- auth_provider: 认证提供者
"""

from .cache_provider import ICacheProvider
from .config_provider import IConfigProvider

__all__ = [
    "IConfigProvider",
    "ICacheProvider",
]

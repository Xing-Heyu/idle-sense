"""
interfaces - 接口定义模块

基于领域驱动设计(DDD)的接口层，包含：
- repositories: 仓储接口
- services: 服务接口
- providers: 提供者接口
"""

from .providers import ICacheProvider, IConfigProvider
from .repositories import INodeRepository, ITaskRepository, IUserRepository
from .services import ISchedulerService, ITaskService

__all__ = [
    # 仓储接口
    "IUserRepository",
    "ITaskRepository",
    "INodeRepository",
    # 服务接口
    "ISchedulerService",
    "ITaskService",
    # 提供者接口
    "IConfigProvider",
    "ICacheProvider",
]

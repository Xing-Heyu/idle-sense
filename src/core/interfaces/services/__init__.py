"""
services - 服务接口模块

定义业务服务接口：
- scheduler_service: 调度器服务
- task_service: 任务服务
- node_service: 节点服务
"""

from .scheduler_service import ISchedulerService
from .task_service import ITaskService

__all__ = [
    "ISchedulerService",
    "ITaskService",
]

"""
external - 外部服务集成模块

包含：
- scheduler_client: 调度器API客户端
- http_client: HTTP客户端基类
"""

from .scheduler_client import (
    DistributedTaskClient,
    HealthInfo,
    NodeInfo,
    SchedulerClient,
)

__all__ = [
    "SchedulerClient",
    "DistributedTaskClient",
    "NodeInfo",
    "HealthInfo",
]

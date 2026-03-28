"""
repositories - 仓储接口模块

定义数据访问接口：
- user_repository: 用户仓储
- task_repository: 任务仓储
- node_repository: 节点仓储
"""

from .node_repository import INodeRepository
from .task_repository import ITaskRepository
from .user_repository import IUserRepository

__all__ = [
    "IUserRepository",
    "ITaskRepository",
    "INodeRepository",
]

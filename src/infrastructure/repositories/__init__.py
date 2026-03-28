"""
repositories - 仓储实现模块

提供多种存储后端实现：
- InMemory: 内存存储（开发/测试）
- SQLite: 本地持久化存储（单节点生产）
- Redis: 分布式存储（多节点生产）
"""

from .node_repository import InMemoryNodeRepository
from .redis_node_repository import RedisNodeRepository
from .redis_task_repository import RedisTaskRepository
from .sqlite_node_repository import SQLiteNodeRepository
from .sqlite_task_repository import SQLiteTaskRepository
from .task_repository import InMemoryTaskRepository
from .user_repository import FileUserRepository

__all__ = [
    "FileUserRepository",
    "InMemoryTaskRepository",
    "InMemoryNodeRepository",
    "SQLiteNodeRepository",
    "SQLiteTaskRepository",
    "RedisNodeRepository",
    "RedisTaskRepository",
]

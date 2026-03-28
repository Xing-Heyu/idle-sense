"""
entities - 实体模块

包含：
- user: 用户实体
- task: 任务实体
- node: 节点实体
- folder: 文件夹实体
"""

from .folder import (
    FOLDER_TYPE_DESCRIPTIONS,
    FOLDER_TYPE_NAMES,
    Folder,
    FolderFactory,
    FolderPermission,
    FolderType,
)
from .node import Node, NodeFactory, NodePlatform, NodeStatus
from .task import Task, TaskFactory, TaskStatus, TaskType
from .user import User, UserFactory

__all__ = [
    "User",
    "UserFactory",
    "Task",
    "TaskStatus",
    "TaskType",
    "TaskFactory",
    "Node",
    "NodeStatus",
    "NodePlatform",
    "NodeFactory",
    "Folder",
    "FolderType",
    "FolderPermission",
    "FolderFactory",
    "FOLDER_TYPE_DESCRIPTIONS",
    "FOLDER_TYPE_NAMES"
]

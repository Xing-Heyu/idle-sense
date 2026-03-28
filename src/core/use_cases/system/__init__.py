"""
system - 系统用例模块

包含：
- get_system_stats_use_case: 获取系统统计用例
- create_folders_use_case: 创建文件夹用例
"""

from .create_folders_use_case import (
    CreateFoldersRequest,
    CreateFoldersResponse,
    CreateFoldersUseCase,
    FolderService,
)
from .get_system_stats_use_case import (
    GetSystemStatsRequest,
    GetSystemStatsResponse,
    GetSystemStatsUseCase,
)

__all__ = [
    "GetSystemStatsUseCase",
    "GetSystemStatsRequest",
    "GetSystemStatsResponse",
    "CreateFoldersUseCase",
    "CreateFoldersRequest",
    "CreateFoldersResponse",
    "FolderService",
]

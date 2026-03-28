"""
src - 源代码目录

基于 Clean Architecture 的分层架构：
- core: 核心业务层（实体、接口、用例）
- infrastructure: 基础设施层（仓储实现、服务实现）
- application: 应用层（DTO、映射器、事件）
- presentation: 表示层（UI组件）
- di: 依赖注入容器
- api: 统一 API 入口
"""

__version__ = "2.0.0"

from src.api import NodeAPI, SchedulerAPI, TaskAPI, UserAPI
from src.core.exceptions import (
    IdleSenseError,
    NodeError,
    NodeNotFoundError,
    NodeOfflineError,
    PermissionDeniedError,
    SchedulerError,
    SecurityError,
    TaskError,
    TaskExecutionError,
    TaskNotFoundError,
    TaskTimeoutError,
    ValidationError,
)

__all__ = [
    "SchedulerAPI",
    "NodeAPI",
    "TaskAPI",
    "UserAPI",
    "IdleSenseError",
    "TaskError",
    "TaskNotFoundError",
    "TaskTimeoutError",
    "TaskExecutionError",
    "NodeError",
    "NodeNotFoundError",
    "NodeOfflineError",
    "SchedulerError",
    "SecurityError",
    "ValidationError",
    "PermissionDeniedError",
]

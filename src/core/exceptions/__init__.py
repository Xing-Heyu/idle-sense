"""
统一异常处理模块

提供 Idle-Sense 项目的统一异常层次结构
"""

from src.core.exceptions.base import IdleSenseError
from src.core.exceptions.node import NodeError, NodeNotFoundError, NodeOfflineError
from src.core.exceptions.registration import (
    RegistrationError,
    RegistrationPermissionError,
    StorageError,
    UserDataConflictError,
    UsernameValidationError,
)
from src.core.exceptions.scheduler import (
    NoAvailableNodeError,
    SchedulerError,
    TaskAssignmentError,
)
from src.core.exceptions.security import (
    PermissionDeniedError,
    SecurityError,
    ValidationError,
)
from src.core.exceptions.task import (
    TaskError,
    TaskExecutionError,
    TaskNotFoundError,
    TaskTimeoutError,
)

__all__ = [
    "IdleSenseError",
    "TaskError",
    "TaskNotFoundError",
    "TaskTimeoutError",
    "TaskExecutionError",
    "NodeError",
    "NodeNotFoundError",
    "NodeOfflineError",
    "SchedulerError",
    "TaskAssignmentError",
    "NoAvailableNodeError",
    "SecurityError",
    "ValidationError",
    "PermissionDeniedError",
    "RegistrationError",
    "UsernameValidationError",
    "StorageError",
    "RegistrationPermissionError",
    "UserDataConflictError",
]

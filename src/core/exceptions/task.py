"""
任务相关异常类模块
"""

from typing import Any, Optional

from src.core.exceptions.base import IdleSenseError


class TaskError(IdleSenseError):
    """
    任务相关错误基类
    """

    def __init__(
        self,
        message: str,
        code: str = "TASK_ERROR",
        task_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        details = details or {}
        if task_id:
            details["task_id"] = task_id
        super().__init__(message, code, details)


class TaskNotFoundError(TaskError):
    """
    任务不存在错误
    """

    def __init__(
        self,
        task_id: str,
        message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        message = message or f"任务不存在: {task_id}"
        super().__init__(message, "TASK_NOT_FOUND", task_id, details)


class TaskTimeoutError(TaskError):
    """
    任务超时错误
    """

    def __init__(
        self,
        task_id: str,
        timeout: int,
        message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        message = message or f"任务执行超时: {task_id} (超时: {timeout}秒)"
        details = details or {}
        details["timeout"] = timeout
        super().__init__(message, "TASK_TIMEOUT", task_id, details)


class TaskExecutionError(TaskError):
    """
    任务执行错误
    """

    def __init__(
        self,
        task_id: str,
        message: str,
        original_error: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        details = details or {}
        if original_error:
            details["original_error"] = original_error
        super().__init__(message, "TASK_EXECUTION_ERROR", task_id, details)


__all__ = ["TaskError", "TaskNotFoundError", "TaskTimeoutError", "TaskExecutionError"]

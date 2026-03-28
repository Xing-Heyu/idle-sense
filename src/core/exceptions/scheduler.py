"""
调度器相关异常类模块
"""

from typing import Any, Optional

from src.core.exceptions.base import IdleSenseError


class SchedulerError(IdleSenseError):
    """
    调度器相关错误基类
    """

    def __init__(
        self,
        message: str,
        code: str = "SCHEDULER_ERROR",
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, code, details)


class TaskAssignmentError(SchedulerError):
    """
    任务分配错误
    """

    def __init__(
        self,
        task_id: str,
        reason: str,
        message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        message = message or f"任务分配失败: {task_id} - {reason}"
        details = details or {}
        details["task_id"] = task_id
        details["reason"] = reason
        super().__init__(message, "TASK_ASSIGNMENT_ERROR", details)


class NoAvailableNodeError(SchedulerError):
    """
    无可用节点错误
    """

    def __init__(
        self,
        task_id: Optional[str] = None,
        message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        message = message or "没有可用的计算节点"
        details = details or {}
        if task_id:
            details["task_id"] = task_id
        super().__init__(message, "NO_AVAILABLE_NODE", details)


__all__ = ["SchedulerError", "TaskAssignmentError", "NoAvailableNodeError"]

"""
监控任务用例

使用示例：
    from src.core.use_cases.task import MonitorTaskUseCase, MonitorTaskRequest

    use_case = MonitorTaskUseCase(task_repository, scheduler_service)
    response = use_case.execute(MonitorTaskRequest(user_id="user_123"))

    if response.success:
        for task in response.tasks:
            print(f"任务: {task.task_id}, 状态: {task.status}")
"""

from dataclasses import dataclass
from typing import Any, Optional

from src.core.entities import TaskStatus
from src.core.interfaces.repositories import ITaskRepository
from src.core.interfaces.services import ISchedulerService


@dataclass
class MonitorTaskRequest:
    """监控任务请求"""
    user_id: Optional[str] = None
    status: Optional[TaskStatus] = None
    limit: int = 100


@dataclass
class MonitorTaskResponse:
    """监控任务响应"""
    success: bool
    tasks: list[dict[str, Any]] = None
    message: str = ""

    def __post_init__(self):
        if self.tasks is None:
            self.tasks = []


class MonitorTaskUseCase:
    """监控任务用例"""

    def __init__(
        self,
        task_repository: ITaskRepository,
        scheduler_service: ISchedulerService
    ):
        """
        初始化监控任务用例

        Args:
            task_repository: 任务仓储
            scheduler_service: 调度器服务
        """
        self._task_repository = task_repository
        self._scheduler_service = scheduler_service

    def execute(self, request: MonitorTaskRequest) -> MonitorTaskResponse:
        """
        执行监控任务

        Args:
            request: 监控任务请求

        Returns:
            监控任务响应
        """
        # 从本地存储获取用户任务
        if request.user_id:
            local_tasks = self._task_repository.list_by_user(request.user_id, request.limit)
        else:
            local_tasks = self._task_repository.list_all(request.limit)

        # 聚合任务状态
        tasks_data = []
        for task in local_tasks:
            # 从调度器获取最新状态
            success, status_data = self._scheduler_service.get_task_status(task.task_id)

            if success:
                # 更新本地任务状态
                task.status = TaskStatus(status_data.get("status", "pending"))
                self._task_repository.update(task)

            tasks_data.append({
                "task_id": task.task_id,
                "status": task.status.value,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "duration": task.duration,
                "result": task.result,
                "error": task.error
            })

        return MonitorTaskResponse(
            success=True,
            tasks=tasks_data
        )


__all__ = ["MonitorTaskUseCase", "MonitorTaskRequest", "MonitorTaskResponse"]

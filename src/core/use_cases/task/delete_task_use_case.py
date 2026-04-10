"""
删除任务用例
"""

from dataclasses import dataclass
from typing import Optional

from src.core.interfaces.repositories import ITaskRepository
from src.core.interfaces.services import ISchedulerService


@dataclass
class DeleteTaskRequest:
    """删除任务请求"""

    task_id: str
    user_id: Optional[str] = None


@dataclass
class DeleteTaskResponse:
    """删除任务响应"""

    success: bool
    message: str = ""


class DeleteTaskUseCase:
    """删除任务用例"""

    def __init__(self, task_repository: ITaskRepository, scheduler_service: ISchedulerService):
        self._task_repository = task_repository
        self._scheduler_service = scheduler_service

    def execute(self, request: DeleteTaskRequest) -> DeleteTaskResponse:
        """执行删除任务"""
        # 验证任务所有权
        task = self._task_repository.get_by_id(request.task_id)

        if task and request.user_id and task.user_id != request.user_id:
            return DeleteTaskResponse(success=False, message="无权限删除此任务")

        # 从调度器删除
        self._scheduler_service.delete_task(request.task_id)

        # 从本地存储删除
        if task:
            self._task_repository.delete(request.task_id)

        return DeleteTaskResponse(success=True, message="任务删除成功")


__all__ = ["DeleteTaskUseCase", "DeleteTaskRequest", "DeleteTaskResponse"]

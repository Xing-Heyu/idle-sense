"""
取消任务用例

使用示例：
    from src.core.use_cases.task import CancelTaskUseCase, CancelTaskRequest

    use_case = CancelTaskUseCase(task_repository, scheduler_service)
    response = use_case.execute(CancelTaskRequest(
        task_id="task_001",
        user_id="user_001"
    ))

    if response.success:
        print(f"任务取消成功: {response.task.status}")
"""

from dataclasses import dataclass
from typing import Optional

from src.core.entities import Task
from src.core.interfaces.repositories import ITaskRepository
from src.core.interfaces.services import ISchedulerService


@dataclass
class CancelTaskRequest:
    """取消任务请求"""

    task_id: str
    user_id: Optional[str] = None


@dataclass
class CancelTaskResponse:
    """取消任务响应"""

    success: bool
    message: str = ""
    task: Optional[Task] = None


class CancelTaskUseCase:
    """取消任务用例"""

    def __init__(self, task_repository: ITaskRepository, scheduler_service: ISchedulerService):
        """
        初始化取消任务用例

        Args:
            task_repository: 任务仓储
            scheduler_service: 调度器服务
        """
        self._task_repository = task_repository
        self._scheduler_service = scheduler_service

    def execute(self, request: CancelTaskRequest) -> CancelTaskResponse:
        """
        执行取消任务

        Args:
            request: 取消任务请求

        Returns:
            取消任务响应
        """
        # 查找任务
        task = self._task_repository.get_by_id(request.task_id)

        if not task:
            return CancelTaskResponse(success=False, message=f"任务ID '{request.task_id}' 不存在")

        # 验证任务所有权
        if request.user_id and task.user_id != request.user_id:
            return CancelTaskResponse(success=False, message="无权限取消此任务")

        # 检查任务状态
        if task.is_completed or task.is_failed:
            return CancelTaskResponse(success=False, message="任务已完成或失败，无法取消")

        if task.is_cancelled:
            return CancelTaskResponse(success=True, task=task, message="任务已处于取消状态")

        # 从调度器取消任务
        scheduler_result = self._scheduler_service.cancel_task(request.task_id)

        if not scheduler_result[0]:
            return CancelTaskResponse(
                success=False,
                message=f"调度器取消任务失败: {scheduler_result[1].get('error', '未知错误')}",
            )

        # 更新任务状态
        task.cancel()
        self._task_repository.update(task)

        return CancelTaskResponse(success=True, task=task, message="任务取消成功")


__all__ = ["CancelTaskUseCase", "CancelTaskRequest", "CancelTaskResponse"]

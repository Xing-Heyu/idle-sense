"""
获取任务状态用例

使用示例：
    from src.core.use_cases.task import GetTaskStatusUseCase, GetTaskStatusRequest

    use_case = GetTaskStatusUseCase(task_repository, scheduler_service)
    response = use_case.execute(GetTaskStatusRequest(
        user_id="user_001",
        status_filter="running"
    ))

    if response.success:
        print(f"获取到 {len(response.tasks)} 个任务")
        print(f"统计: {response.stats}")
"""

from dataclasses import dataclass
from typing import Any, Optional

from src.core.entities import Task
from src.core.interfaces.repositories import ITaskRepository
from src.core.interfaces.services import ISchedulerService


@dataclass
class GetTaskStatusRequest:
    """获取任务状态请求"""

    user_id: Optional[str] = None
    task_id: Optional[str] = None
    status_filter: Optional[str] = None


@dataclass
class GetTaskStatusResponse:
    """获取任务状态响应"""

    success: bool
    tasks: list[Task] = None
    message: str = ""
    stats: Optional[dict[str, Any]] = None


class GetTaskStatusUseCase:
    """获取任务状态用例"""

    def __init__(self, task_repository: ITaskRepository, scheduler_service: ISchedulerService):
        """
        初始化获取任务状态用例

        Args:
            task_repository: 任务仓储
            scheduler_service: 调度器服务
        """
        self._task_repository = task_repository
        self._scheduler_service = scheduler_service

    def execute(self, request: GetTaskStatusRequest) -> GetTaskStatusResponse:
        """
        执行获取任务状态

        Args:
            request: 获取任务状态请求

        Returns:
            获取任务状态响应
        """
        # 如果指定了任务ID，只获取单个任务
        if request.task_id:
            task = self._task_repository.get_by_id(request.task_id)
            if not task:
                return GetTaskStatusResponse(
                    success=False, message=f"任务ID '{request.task_id}' 不存在"
                )

            # 验证所有权
            if request.user_id and task.user_id != request.user_id:
                return GetTaskStatusResponse(success=False, message="无权限查看此任务")

            return GetTaskStatusResponse(success=True, tasks=[task], message="获取任务状态成功")

        # 获取任务列表
        if request.user_id:
            tasks = self._task_repository.list_by_user(request.user_id)
        else:
            tasks = self._task_repository.list_all()

        # 状态过滤
        if request.status_filter:
            tasks = [t for t in tasks if t.status.value == request.status_filter]

        # 收集统计信息
        stats = {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t.is_pending),
            "running": sum(1 for t in tasks if t.is_running),
            "completed": sum(1 for t in tasks if t.is_completed),
            "failed": sum(1 for t in tasks if t.is_failed),
            "cancelled": sum(1 for t in tasks if t.is_cancelled),
        }

        return GetTaskStatusResponse(
            success=True, tasks=tasks, stats=stats, message="获取任务状态成功"
        )


__all__ = ["GetTaskStatusUseCase", "GetTaskStatusRequest", "GetTaskStatusResponse"]

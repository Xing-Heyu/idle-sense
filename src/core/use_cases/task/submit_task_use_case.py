"""
提交任务用例

使用示例：
    from src.core.use_cases.task import SubmitTaskUseCase, SubmitTaskRequest

    use_case = SubmitTaskUseCase(task_repository, scheduler_service)
    response = use_case.execute(SubmitTaskRequest(
        code="print('hello')",
        timeout=300,
        cpu=1.0,
        memory=512
    ))

    if response.success:
        print(f"任务提交成功: {response.task_id}")
"""

from dataclasses import dataclass
from typing import Optional

from src.core.entities import TaskFactory
from src.core.interfaces.repositories import ITaskRepository
from src.core.interfaces.services import ISchedulerService


@dataclass
class SubmitTaskRequest:
    """提交任务请求"""
    code: str
    user_id: Optional[str] = None
    timeout: int = 300
    cpu: float = 1.0
    memory: int = 512


@dataclass
class SubmitTaskResponse:
    """提交任务响应"""
    success: bool
    task_id: str = ""
    message: str = ""


class SubmitTaskUseCase:
    """提交任务用例"""

    def __init__(
        self,
        task_repository: ITaskRepository,
        scheduler_service: ISchedulerService
    ):
        """
        初始化提交任务用例

        Args:
            task_repository: 任务仓储
            scheduler_service: 调度器服务
        """
        self._task_repository = task_repository
        self._scheduler_service = scheduler_service

    def execute(self, request: SubmitTaskRequest) -> SubmitTaskResponse:
        """
        执行提交任务

        Args:
            request: 提交任务请求

        Returns:
            提交任务响应
        """
        # 创建任务实体
        task = TaskFactory.create(
            code=request.code,
            user_id=request.user_id,
            timeout=request.timeout,
            cpu=request.cpu,
            memory=request.memory
        )

        # 提交到调度器
        scheduler_result = self._scheduler_service.submit_task(
            code=task.code,
            timeout=task.timeout,
            cpu=task.cpu_request,
            memory=task.memory_request,
            user_id=task.user_id
        )

        if not scheduler_result[0]:
            return SubmitTaskResponse(
                success=False,
                message=f"提交到调度器失败: {scheduler_result[1].get('error', '未知错误')}"
            )

        # 更新任务ID并保存
        task.task_id = scheduler_result[1].get("task_id", task.task_id)
        self._task_repository.save(task)

        return SubmitTaskResponse(
            success=True,
            task_id=task.task_id,
            message="任务提交成功"
        )


__all__ = ["SubmitTaskUseCase", "SubmitTaskRequest", "SubmitTaskResponse"]

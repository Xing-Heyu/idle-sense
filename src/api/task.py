"""
任务 API

提供任务相关的统一接口
"""

from typing import Any, Optional

from src.core.use_cases.task.cancel_task_use_case import CancelTaskUseCase
from src.core.use_cases.task.delete_task_use_case import DeleteTaskUseCase
from src.core.use_cases.task.get_task_status_use_case import GetTaskStatusUseCase
from src.core.use_cases.task.monitor_task_use_case import MonitorTaskUseCase
from src.core.use_cases.task.submit_task_use_case import SubmitTaskUseCase
from src.infrastructure.external.scheduler_client import SchedulerClient


class TaskAPI:
    """
    任务 API

    提供任务操作的统一接口
    """

    def __init__(
        self,
        client: Optional[SchedulerClient] = None,
        base_url: str = "http://localhost:8000",
    ):
        self._client = client or SchedulerClient(base_url=base_url)

    def submit(
        self,
        code: str,
        timeout: int = 300,
        resources: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """提交任务"""
        use_case = SubmitTaskUseCase(self._client)
        return use_case.execute(code, timeout, resources, user_id)

    def get_status(self, task_id: str) -> dict[str, Any]:
        """获取任务状态"""
        use_case = GetTaskStatusUseCase(self._client)
        return use_case.execute(task_id)

    def cancel(self, task_id: str) -> bool:
        """取消任务"""
        use_case = CancelTaskUseCase(self._client)
        return use_case.execute(task_id)

    def delete(self, task_id: str) -> bool:
        """删除任务"""
        use_case = DeleteTaskUseCase(self._client)
        return use_case.execute(task_id)

    def monitor(self, task_ids: Optional[list[str]] = None) -> list[dict[str, Any]]:
        """监控任务"""
        use_case = MonitorTaskUseCase(self._client)
        return use_case.execute(task_ids)

    def get_results(self) -> list[dict[str, Any]]:
        """获取所有任务结果"""
        return self._client.get_results()


__all__ = ["TaskAPI"]

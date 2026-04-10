"""
获取系统统计用例

使用示例：
    from src.core.use_cases.system import GetSystemStatsUseCase, GetSystemStatsRequest

    use_case = GetSystemStatsUseCase(
        user_repository,
        task_repository,
        node_repository,
        scheduler_service
    )
    response = use_case.execute(GetSystemStatsRequest())

    if response.success:
        print(f"系统统计: {response.stats}")
"""

from dataclasses import dataclass
from typing import Any

from src.core.interfaces.repositories import INodeRepository, ITaskRepository, IUserRepository
from src.core.interfaces.services import ISchedulerService


@dataclass
class GetSystemStatsRequest:
    """获取系统统计请求"""

    include_details: bool = False


@dataclass
class GetSystemStatsResponse:
    """获取系统统计响应"""

    success: bool
    stats: dict[str, Any] = None
    message: str = ""


class GetSystemStatsUseCase:
    """获取系统统计用例"""

    def __init__(
        self,
        user_repository: IUserRepository,
        task_repository: ITaskRepository,
        node_repository: INodeRepository,
        scheduler_service: ISchedulerService,
    ):
        """
        初始化获取系统统计用例

        Args:
            user_repository: 用户仓储
            task_repository: 任务仓储
            node_repository: 节点仓储
            scheduler_service: 调度器服务
        """
        self._user_repository = user_repository
        self._task_repository = task_repository
        self._node_repository = node_repository
        self._scheduler_service = scheduler_service

    def execute(self, request: GetSystemStatsRequest) -> GetSystemStatsResponse:
        """
        执行获取系统统计

        Args:
            request: 获取系统统计请求

        Returns:
            获取系统统计响应
        """
        try:
            # 用户统计
            users = self._user_repository.list_all()
            user_stats = {
                "total": len(users),
                "active": sum(1 for u in users if u.is_active),
            }

            # 任务统计
            tasks = self._task_repository.list_all()
            task_stats = {
                "total": len(tasks),
                "pending": sum(1 for t in tasks if t.is_pending),
                "running": sum(1 for t in tasks if t.is_running),
                "completed": sum(1 for t in tasks if t.is_completed),
                "failed": sum(1 for t in tasks if t.is_failed),
                "cancelled": sum(1 for t in tasks if t.is_cancelled),
            }

            # 节点统计
            nodes = self._node_repository.list_all()
            node_stats = {
                "total": len(nodes),
                "online": sum(1 for n in nodes if n.is_online),
                "idle": sum(1 for n in nodes if n.is_idle),
                "busy": sum(1 for n in nodes if n.status.value == "busy"),
            }

            # 调度器统计
            scheduler_result = self._scheduler_service.get_queue_status()
            scheduler_stats = {}
            if scheduler_result[0]:
                scheduler_stats = scheduler_result[1].get("stats", {})

            # 资源统计
            total_cpu = sum(n.cpu_limit for n in nodes if n.is_online)
            total_memory = sum(n.memory_limit for n in nodes if n.is_online)
            used_cpu = sum(n.used_cpu for n in nodes if n.is_online)
            used_memory = sum(n.used_memory for n in nodes if n.is_online)

            resource_stats = {
                "total_cpu": total_cpu,
                "total_memory": total_memory,
                "used_cpu": used_cpu,
                "used_memory": used_memory,
                "available_cpu": total_cpu - used_cpu,
                "available_memory": total_memory - used_memory,
            }

            # 汇总统计
            stats = {
                "users": user_stats,
                "tasks": task_stats,
                "nodes": node_stats,
                "scheduler": scheduler_stats,
                "resources": resource_stats,
            }

            # 详细信息
            if request.include_details:
                stats["users_list"] = [
                    {"user_id": u.user_id, "username": u.username} for u in users
                ]
                stats["nodes_list"] = [
                    {"node_id": n.node_id, "status": n.status.value} for n in nodes
                ]

            return GetSystemStatsResponse(success=True, stats=stats, message="获取系统统计成功")

        except Exception as e:
            return GetSystemStatsResponse(success=False, message=f"获取系统统计失败: {str(e)}")


__all__ = ["GetSystemStatsUseCase", "GetSystemStatsRequest", "GetSystemStatsResponse"]

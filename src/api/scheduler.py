"""
调度器 API

提供调度器相关的统一接口
"""

from typing import Any, Optional

from src.infrastructure.external.scheduler_client import SchedulerClient


class SchedulerAPI:
    """
    调度器 API

    提供调度器操作的统一接口
    """

    def __init__(
        self, client: Optional[SchedulerClient] = None, base_url: str = "http://localhost:8000"
    ):
        self._client = client or SchedulerClient(base_url=base_url)

    def check_health(self) -> dict[str, Any]:
        """检查调度器健康状态"""
        return self._client.check_health()

    def get_stats(self) -> dict[str, Any]:
        """获取调度器统计信息"""
        return self._client.get_stats()

    def get_nodes(self) -> list[dict[str, Any]]:
        """获取所有节点列表"""
        return self._client.get_nodes()

    def get_pending_tasks(self) -> list[dict[str, Any]]:
        """获取待处理任务列表"""
        return self._client.get_pending_tasks()

    def register_node(
        self,
        node_id: str,
        capacity: dict[str, Any],
        tags: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """注册节点"""
        return self._client.register_node(node_id, capacity, tags)

    def update_heartbeat(
        self,
        node_id: str,
        heartbeat_data: dict[str, Any],
    ) -> bool:
        """更新节点心跳"""
        return self._client.update_heartbeat(node_id, heartbeat_data)


__all__ = ["SchedulerAPI"]

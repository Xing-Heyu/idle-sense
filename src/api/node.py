"""
节点 API

提供节点相关的统一接口
"""

from typing import Any, Optional

from src.core.use_cases.node.activate_node_use_case import ActivateNodeUseCase
from src.core.use_cases.node.get_node_status_use_case import GetNodeStatusUseCase
from src.core.use_cases.node.stop_node_use_case import StopNodeUseCase
from src.infrastructure.external.scheduler_client import SchedulerClient


class NodeAPI:
    """
    节点 API

    提供节点操作的统一接口
    """

    def __init__(
        self,
        client: Optional[SchedulerClient] = None,
        base_url: str = "http://localhost:8000",
    ):
        self._client = client or SchedulerClient(base_url=base_url)

    def activate(
        self,
        node_id: str,
        capacity: dict[str, Any],
        tags: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """激活节点"""
        use_case = ActivateNodeUseCase(self._client)
        return use_case.execute(node_id, capacity, tags)

    def get_status(self, node_id: str) -> dict[str, Any]:
        """获取节点状态"""
        use_case = GetNodeStatusUseCase(self._client)
        return use_case.execute(node_id)

    def stop(self, node_id: str) -> bool:
        """停止节点"""
        use_case = StopNodeUseCase(self._client)
        return use_case.execute(node_id)

    def list_all(self) -> list[dict[str, Any]]:
        """获取所有节点列表"""
        return self._client.get_nodes()

    def update_heartbeat(
        self,
        node_id: str,
        heartbeat_data: dict[str, Any],
    ) -> bool:
        """更新节点心跳"""
        return self._client.update_heartbeat(node_id, heartbeat_data)


__all__ = ["NodeAPI"]

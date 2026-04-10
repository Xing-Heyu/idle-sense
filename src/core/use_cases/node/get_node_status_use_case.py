"""
获取节点状态用例

使用示例：
    from src.core.use_cases.node import GetNodeStatusUseCase, GetNodeStatusRequest

    use_case = GetNodeStatusUseCase(node_repository, scheduler_service)
    response = use_case.execute(GetNodeStatusRequest(
        online_only=True
    ))

    if response.success:
        print(f"获取到 {len(response.nodes)} 个节点")
"""

from dataclasses import dataclass
from typing import Any, Optional

from src.core.entities import Node, NodeFactory
from src.core.interfaces.repositories import INodeRepository
from src.core.interfaces.services import ISchedulerService


@dataclass
class GetNodeStatusRequest:
    """获取节点状态请求"""

    online_only: bool = False
    node_id: Optional[str] = None


@dataclass
class GetNodeStatusResponse:
    """获取节点状态响应"""

    success: bool
    nodes: list[Node] = None
    message: str = ""
    stats: Optional[dict[str, Any]] = None


class GetNodeStatusUseCase:
    """获取节点状态用例"""

    def __init__(self, node_repository: INodeRepository, scheduler_service: ISchedulerService):
        """
        初始化获取节点状态用例

        Args:
            node_repository: 节点仓储
            scheduler_service: 调度器服务
        """
        self._node_repository = node_repository
        self._scheduler_service = scheduler_service

    def execute(self, request: GetNodeStatusRequest) -> GetNodeStatusResponse:
        """
        执行获取节点状态

        Args:
            request: 获取节点状态请求

        Returns:
            获取节点状态响应
        """
        # 如果指定了节点ID，只获取单个节点
        if request.node_id:
            node = self._node_repository.get_by_id(request.node_id)
            if not node:
                return GetNodeStatusResponse(
                    success=False, message=f"节点ID '{request.node_id}' 不存在"
                )

            # 从调度器获取最新状态
            scheduler_result = self._scheduler_service.get_nodes(online_only=False)

            if scheduler_result[0]:
                nodes_data = scheduler_result[1].get("nodes", [])
                for node_data in nodes_data:
                    if node_data.get("node_id") == request.node_id:
                        # 更新节点状态
                        updated_node = NodeFactory.create_from_dict(node_data)
                        self._node_repository.update(updated_node)
                        return GetNodeStatusResponse(
                            success=True, nodes=[updated_node], message="获取节点状态成功"
                        )

            return GetNodeStatusResponse(success=True, nodes=[node], message="获取节点状态成功")

        # 从调度器获取所有节点
        scheduler_result = self._scheduler_service.get_nodes(online_only=request.online_only)

        if not scheduler_result[0]:
            return GetNodeStatusResponse(
                success=False,
                message=f"从调度器获取节点失败: {scheduler_result[1].get('error', '未知错误')}",
            )

        nodes_data = scheduler_result[1].get("nodes", [])
        nodes = []

        for node_data in nodes_data:
            try:
                node = NodeFactory.create_from_dict(node_data)
                nodes.append(node)
                # 更新本地仓储
                existing_node = self._node_repository.get_by_id(node.node_id)
                if existing_node:
                    self._node_repository.update(node)
                else:
                    self._node_repository.save(node)
            except Exception:
                continue

        # 收集统计信息
        stats = {
            "total": len(nodes),
            "online": sum(1 for n in nodes if n.is_online),
            "idle": sum(1 for n in nodes if n.is_idle),
            "busy": sum(1 for n in nodes if n.status.value == "busy"),
        }

        return GetNodeStatusResponse(
            success=True, nodes=nodes, stats=stats, message="获取节点状态成功"
        )


__all__ = ["GetNodeStatusUseCase", "GetNodeStatusRequest", "GetNodeStatusResponse"]

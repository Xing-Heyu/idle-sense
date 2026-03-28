"""
停止节点用例

使用示例：
    from src.core.use_cases.node import StopNodeUseCase, StopNodeRequest

    use_case = StopNodeUseCase(node_repository, scheduler_service)
    response = use_case.execute(StopNodeRequest(
        node_id="node_001"
    ))

    if response.success:
        print(f"节点停止成功: {response.node_id}")
"""

from dataclasses import dataclass
from typing import Optional

from src.core.entities import Node
from src.core.interfaces.repositories import INodeRepository
from src.core.interfaces.services import ISchedulerService


@dataclass
class StopNodeRequest:
    """停止节点请求"""
    node_id: str


@dataclass
class StopNodeResponse:
    """停止节点响应"""
    success: bool
    node_id: str = ""
    message: str = ""
    node: Optional[Node] = None


class StopNodeUseCase:
    """停止节点用例"""

    def __init__(
        self,
        node_repository: INodeRepository,
        scheduler_service: ISchedulerService
    ):
        """
        初始化停止节点用例

        Args:
            node_repository: 节点仓储
            scheduler_service: 调度器服务
        """
        self._node_repository = node_repository
        self._scheduler_service = scheduler_service

    def execute(self, request: StopNodeRequest) -> StopNodeResponse:
        """
        执行停止节点

        Args:
            request: 停止节点请求

        Returns:
            停止节点响应
        """
        # 查找节点
        node = self._node_repository.get_by_id(request.node_id)

        if not node:
            return StopNodeResponse(
                success=False,
                node_id=request.node_id,
                message=f"节点ID '{request.node_id}' 不存在"
            )

        # 停止调度器中的节点
        scheduler_result = self._scheduler_service.stop_node(request.node_id)

        if not scheduler_result[0]:
            return StopNodeResponse(
                success=False,
                node_id=request.node_id,
                message=f"停止调度器节点失败: {scheduler_result[1].get('error', '未知错误')}"
            )

        # 更新节点状态
        node.go_offline()
        self._node_repository.update(node)

        return StopNodeResponse(
            success=True,
            node_id=node.node_id,
            node=node,
            message="节点停止成功"
        )


__all__ = ["StopNodeUseCase", "StopNodeRequest", "StopNodeResponse"]

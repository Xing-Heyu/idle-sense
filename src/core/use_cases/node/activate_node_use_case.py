"""
激活节点用例

使用示例：
    from src.core.use_cases.node import ActivateNodeUseCase, ActivateNodeRequest

    use_case = ActivateNodeUseCase(node_repository, scheduler_service)
    response = use_case.execute(ActivateNodeRequest(
        cpu_limit=4.0,
        memory_limit=8192,
        storage_limit=10240,
        user_id="user_001"
    ))

    if response.success:
        print(f"节点激活成功: {response.node_id}")
"""

from dataclasses import dataclass
from typing import Optional

from src.core.entities import Node, NodeFactory
from src.core.interfaces.repositories import INodeRepository
from src.core.interfaces.services import ISchedulerService


@dataclass
class ActivateNodeRequest:
    """激活节点请求"""

    cpu_limit: float
    memory_limit: int
    storage_limit: int
    user_id: Optional[str] = None


@dataclass
class ActivateNodeResponse:
    """激活节点响应"""

    success: bool
    node_id: str = ""
    message: str = ""
    node: Optional[Node] = None


class ActivateNodeUseCase:
    """激活节点用例"""

    def __init__(self, node_repository: INodeRepository, scheduler_service: ISchedulerService):
        """
        初始化激活节点用例

        Args:
            node_repository: 节点仓储
            scheduler_service: 调度器服务
        """
        self._node_repository = node_repository
        self._scheduler_service = scheduler_service

    def execute(self, request: ActivateNodeRequest) -> ActivateNodeResponse:
        """
        执行激活节点

        Args:
            request: 激活节点请求

        Returns:
            激活节点响应
        """
        # 验证资源限制
        if request.cpu_limit <= 0:
            return ActivateNodeResponse(success=False, message="CPU限制必须大于0")

        if request.memory_limit <= 0:
            return ActivateNodeResponse(success=False, message="内存限制必须大于0")

        if request.storage_limit <= 0:
            return ActivateNodeResponse(success=False, message="存储限制必须大于0")

        # 创建节点实体
        node = NodeFactory.create_local(
            cpu_limit=request.cpu_limit,
            memory_limit=request.memory_limit,
            storage_limit=request.storage_limit,
            user_id=request.user_id,
        )

        # 激活到调度器
        scheduler_result = self._scheduler_service.activate_local_node(
            cpu_limit=request.cpu_limit,
            memory_limit=request.memory_limit,
            storage_limit=request.storage_limit,
            user_id=request.user_id,
        )

        if not scheduler_result[0]:
            return ActivateNodeResponse(
                success=False,
                message=f"激活到调度器失败: {scheduler_result[1].get('error', '未知错误')}",
            )

        # 更新节点ID并保存
        node.node_id = scheduler_result[1].get("node_id", node.node_id)
        node.go_online()
        self._node_repository.save(node)

        return ActivateNodeResponse(
            success=True, node_id=node.node_id, node=node, message="节点激活成功"
        )


__all__ = ["ActivateNodeUseCase", "ActivateNodeRequest", "ActivateNodeResponse"]

"""
节点仓储接口

定义节点数据访问的抽象接口：
- get_by_id: 根据ID获取节点
- save: 保存节点
- update: 更新节点
- list_all: 获取所有节点
- list_online: 获取在线节点
"""

from abc import ABC, abstractmethod
from typing import Optional

from src.core.entities import Node, NodeStatus


class INodeRepository(ABC):
    """
    节点仓储接口

    定义节点数据访问的契约
    """

    @abstractmethod
    def get_by_id(self, node_id: str) -> Optional[Node]:
        """
        根据ID获取节点

        Args:
            node_id: 节点ID

        Returns:
            节点实体，如果不存在则返回None
        """
        pass

    @abstractmethod
    def save(self, node: Node) -> Node:
        """
        保存节点

        Args:
            node: 节点实体

        Returns:
            保存后的节点实体
        """
        pass

    @abstractmethod
    def update(self, node: Node) -> Node:
        """
        更新节点

        Args:
            node: 节点实体

        Returns:
            更新后的节点实体
        """
        pass

    @abstractmethod
    def delete(self, node_id: str) -> bool:
        """
        删除节点

        Args:
            node_id: 节点ID

        Returns:
            是否删除成功
        """
        pass

    @abstractmethod
    def list_all(self) -> list[Node]:
        """
        获取所有节点

        Returns:
            节点实体列表
        """
        pass

    @abstractmethod
    def list_by_status(self, status: NodeStatus) -> list[Node]:
        """
        获取指定状态的节点列表

        Args:
            status: 节点状态

        Returns:
            节点实体列表
        """
        pass

    @abstractmethod
    def list_online(self) -> list[Node]:
        """
        获取所有在线节点

        Returns:
            节点实体列表
        """
        pass

    @abstractmethod
    def list_idle(self) -> list[Node]:
        """
        获取所有空闲节点

        Returns:
            节点实体列表
        """
        pass


__all__ = ["INodeRepository"]

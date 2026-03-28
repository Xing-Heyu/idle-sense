"""
节点仓储实现

基于内存的节点存储
"""

import threading
from typing import Optional

from src.core.entities import Node, NodeStatus
from src.core.interfaces.repositories import INodeRepository


class InMemoryNodeRepository(INodeRepository):
    """基于内存的节点仓储实现"""

    def __init__(self):
        self._nodes: dict[str, Node] = {}
        self._lock = threading.RLock()

    def get_by_id(self, node_id: str) -> Optional[Node]:
        with self._lock:
            return self._nodes.get(node_id)

    def save(self, node: Node) -> Node:
        with self._lock:
            self._nodes[node.node_id] = node
            return node

    def update(self, node: Node) -> Node:
        with self._lock:
            if node.node_id in self._nodes:
                self._nodes[node.node_id] = node
            return node

    def delete(self, node_id: str) -> bool:
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                return True
            return False

    def list_all(self) -> list[Node]:
        with self._lock:
            return list(self._nodes.values())

    def list_by_status(self, status: NodeStatus) -> list[Node]:
        with self._lock:
            return [n for n in self._nodes.values() if n.status == status]

    def list_online(self) -> list[Node]:
        with self._lock:
            return [n for n in self._nodes.values() if n.is_online]

    def list_idle(self) -> list[Node]:
        with self._lock:
            return [n for n in self._nodes.values() if n.is_idle]


__all__ = ["InMemoryNodeRepository"]

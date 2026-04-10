"""
Redis节点仓储实现

提供基于Redis的节点持久化存储
"""

import json
from datetime import datetime
from typing import Optional

from src.core.entities import Node, NodeStatus
from src.core.interfaces.repositories import INodeRepository


class RedisNodeRepository(INodeRepository):
    """
    基于Redis的节点仓储实现

    提供节点数据的持久化存储，支持：
    - 分布式访问
    - 高性能读写
    - TTL自动过期
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "idle_sense:node:",
        ttl: int = 86400,
    ):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.ttl = ttl
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                import redis.asyncio as redis

                self._client = redis.from_url(self.redis_url)
            except ImportError as e:
                raise ImportError(
                    "Redis storage requires the redis package. "
                    "Install it with: pip install redis"
                ) from e
        return self._client

    def _node_to_dict(self, node: Node) -> str:
        return json.dumps(
            {
                "node_id": node.node_id,
                "platform": node.platform,
                "status": node.status.value,
                "capacity": node.capacity,
                "tags": node.tags,
                "owner": node.owner,
                "registered_at": node.registered_at.isoformat() if node.registered_at else None,
                "last_heartbeat": node.last_heartbeat.isoformat() if node.last_heartbeat else None,
                "is_available": node.is_available,
                "is_idle": node.is_idle,
            }
        )

    def _dict_to_node(self, data: str) -> Node:
        obj = json.loads(data)
        return Node(
            node_id=obj["node_id"],
            platform=obj["platform"],
            status=NodeStatus(obj["status"]),
            capacity=obj.get("capacity", {}),
            tags=obj.get("tags", {}),
            owner=obj.get("owner", "unknown"),
            registered_at=(
                datetime.fromisoformat(obj["registered_at"]) if obj.get("registered_at") else None
            ),
            last_heartbeat=(
                datetime.fromisoformat(obj["last_heartbeat"]) if obj.get("last_heartbeat") else None
            ),
            is_available=obj.get("is_available", False),
            is_idle=obj.get("is_idle", False),
        )

    async def get_by_id(self, node_id: str) -> Optional[Node]:
        client = await self._get_client()
        key = f"{self.key_prefix}{node_id}"
        data = await client.get(key)
        return self._dict_to_node(data.decode()) if data else None

    async def save(self, node: Node) -> Node:
        client = await self._get_client()
        key = f"{self.key_prefix}{node.node_id}"
        await client.setex(key, self.ttl, self._node_to_dict(node))
        await client.sadd(f"{self.key_prefix}all", node.node_id)
        await client.sadd(f"{self.key_prefix}status:{node.status.value}", node.node_id)
        return node

    async def update(self, node: Node) -> Node:
        client = await self._get_client()
        old_node = await self.get_by_id(node.node_id)
        if old_node and old_node.status != node.status:
            await client.srem(f"{self.key_prefix}status:{old_node.status.value}", node.node_id)
        return await self.save(node)

    async def delete(self, node_id: str) -> bool:
        client = await self._get_client()
        node = await self.get_by_id(node_id)
        if node:
            await client.delete(f"{self.key_prefix}{node_id}")
            await client.srem(f"{self.key_prefix}all", node_id)
            await client.srem(f"{self.key_prefix}status:{node.status.value}", node_id)
            return True
        return False

    async def list_all(self) -> list[Node]:
        client = await self._get_client()
        node_ids = await client.smembers(f"{self.key_prefix}all")
        nodes = []
        for node_id in node_ids:
            node = await self.get_by_id(node_id.decode())
            if node:
                nodes.append(node)
        return nodes

    async def list_by_status(self, status: NodeStatus) -> list[Node]:
        client = await self._get_client()
        node_ids = await client.smembers(f"{self.key_prefix}status:{status.value}")
        nodes = []
        for node_id in node_ids:
            node = await self.get_by_id(node_id.decode())
            if node:
                nodes.append(node)
        return nodes

    async def list_online(self) -> list[Node]:
        nodes = []
        for status in [NodeStatus.ONLINE, NodeStatus.IDLE, NodeStatus.BUSY]:
            nodes.extend(await self.list_by_status(status))
        return nodes

    async def list_idle(self) -> list[Node]:
        return await self.list_by_status(NodeStatus.IDLE)

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None


__all__ = ["RedisNodeRepository"]

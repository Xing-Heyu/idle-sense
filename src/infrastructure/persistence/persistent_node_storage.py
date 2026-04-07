"""
持久化节点存储模块

包装 SQLiteNodeRepository，提供：
- 内存缓存层加速读取
- 心跳超时自动标记 offline（默认 180 秒）
- 兼容调度器节点管理调用方式的统一接口
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from src.core.entities import Node, NodeStatus
from src.infrastructure.persistence import get_db_path
from src.infrastructure.repositories.sqlite_node_repository import SQLiteNodeRepository
from src.infrastructure.utils.logger import get_logger

logger = get_logger("src.infrastructure.persistence.persistent_node_storage")

_DEFAULT_HEARTBEAT_TIMEOUT = 180


@dataclass
class NodeRegistration:
    """节点注册信息"""
    node_id: str
    capacity: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, Any] = field(default_factory=dict)
    platform: str = "unknown"
    owner: str = "unknown"


@dataclass
class NodeHeartbeat:
    """节点心跳数据"""
    node_id: str
    current_load: dict[str, Any] = field(default_factory=lambda: {"cpu_usage": 0.0, "memory_usage": 0})
    is_idle: bool = True
    is_available: bool = True
    available_resources: dict[str, Any] = field(default_factory=dict)


class PersistentNodeStorage:
    """
    持久化节点存储

    内部使用 SQLiteNodeRepository 做持久化，外层维护内存缓存加速读取。
    所有公开方法均为异步，与底层仓储保持一致。
    """

    def __init__(self, db_path: Optional[str] = None, heartbeat_timeout: int = _DEFAULT_HEARTBEAT_TIMEOUT):
        """
        初始化持久化节点存储

        Args:
            db_path: 数据库文件路径，为空则使用 persistence 模块的默认路径
            heartbeat_timeout: 心跳超时秒数，超过此时间自动标记节点为 offline
        """
        resolved_path = str(db_path) if db_path else str(get_db_path())
        self._repository = SQLiteNodeRepository(db_path=resolved_path)
        self._heartbeat_timeout = heartbeat_timeout
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_lock = threading.RLock()
        self._initialized = False

    async def _ensure_init(self) -> None:
        """确保数据库连接已初始化"""
        if not self._initialized:
            await self._repository._get_connection()
            self._initialized = True

    def _node_to_cache_dict(self, node: Node) -> dict[str, Any]:
        """将 Node 实体转为缓存字典"""
        return {
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

    def _apply_heartbeat_check(self, cached: dict[str, Any]) -> dict[str, Any]:
        """对缓存条目执行心跳超时检查，超时则标记 offline"""
        result = dict(cached)
        last_hb_str = result.get("last_heartbeat")
        if not last_hb_str:
            result["status"] = NodeStatus.OFFLINE.value
            result["is_available"] = False
            return result

        try:
            last_hb = datetime.fromisoformat(last_hb_str)
        except (ValueError, TypeError):
            result["status"] = NodeStatus.OFFLINE.value
            result["is_available"] = False
            return result

        elapsed = (datetime.now() - last_hb).total_seconds()
        if elapsed > self._heartbeat_timeout:
            result["status"] = NodeStatus.OFFLINE.value
            result["is_available"] = False
        return result

    def _invalidate_cache(self, node_id: Optional[str] = None) -> None:
        """失效缓存"""
        with self._cache_lock:
            if node_id:
                self._cache.pop(node_id, None)
            else:
                self._cache.clear()

    async def _refresh_cache(self, node_id: str) -> Optional[dict[str, Any]]:
        """从持久化层刷新单个节点到缓存"""
        await self._ensure_init()
        node = await self._repository.get_by_id(node_id)
        if node is None:
            with self._cache_lock:
                self._cache.pop(node_id, None)
            return None
        cached = self._node_to_cache_dict(node)
        with self._cache_lock:
            self._cache[node_id] = cached
        return cached

    async def register_node(self, registration: NodeRegistration) -> bool:
        """
        注册新节点

        Args:
            registration: 节点注册信息

        Returns:
            注册是否成功
        """
        await self._ensure_init()
        now = datetime.now()
        node = Node(
            node_id=registration.node_id,
            platform=registration.platform,
            status=NodeStatus.ONLINE,
            capacity=registration.capacity,
            tags={str(k): str(v) for k, v in registration.tags.items()},
            owner=registration.owner,
            registered_at=now,
            last_heartbeat=now,
            is_available=True,
            is_idle=True,
        )
        await self._repository.save(node)
        cached = self._node_to_cache_dict(node)
        with self._cache_lock:
            self._cache[registration.node_id] = cached
        logger.info("节点注册成功", node_id=registration.node_id)
        return True

    async def update_node_heartbeat(self, heartbeat: NodeHeartbeat) -> bool:
        """
        更新节点心跳

        Args:
            heartbeat: 节点心跳数据

        Returns:
            更新是否成功
        """
        await self._ensure_init()
        node = await self._repository.get_by_id(heartbeat.node_id)
        if node is None:
            logger.warning("心跳更新失败：节点不存在", node_id=heartbeat.node_id)
            return False

        now = datetime.now()
        node.last_heartbeat = now
        node.is_idle = heartbeat.is_idle
        node.is_available = heartbeat.is_available
        if node.status == NodeStatus.OFFLINE:
            node.status = NodeStatus.ONLINE
        elif heartbeat.is_idle:
            node.status = NodeStatus.IDLE
        else:
            node.status = NodeStatus.BUSY

        node.capacity.update(heartbeat.available_resources)
        await self._repository.save(node)

        cached = self._node_to_cache_dict(node)
        with self._cache_lock:
            self._cache[heartbeat.node_id] = cached
        return True

    async def get_available_nodes(self, include_busy: bool = False) -> list[dict]:
        """
        获取可用节点列表

        Args:
            include_busy: 是否包含忙碌节点

        Returns:
            节点字典列表（已应用心跳超时检查）
        """
        await self._ensure_init()
        all_nodes = await self._repository.list_online()

        result: list[dict] = []
        for node in all_nodes:
            cached = self._node_to_cache_dict(node)
            with self._cache_lock:
                self._cache[node.node_id] = cached

            checked = self._apply_heartbeat_check(cached)
            is_online = checked["status"] != NodeStatus.OFFLINE.value

            if not is_online:
                continue

            if not include_busy and not checked.get("is_idle", False):
                continue

            result.append(checked)

        logger.debug(
            "获取可用节点",
            count=len(result),
            include_busy=include_busy,
        )
        return result

    async def cleanup_dead_nodes(self, timeout_seconds: int = 180) -> int:
        """
        清理超时死亡节点（标记为 offline 并从缓存移除）

        Args:
            timeout_seconds: 超时阈值（秒）

        Returns:
            清理的节点数量
        """
        await self._ensure_init()
        all_nodes = await self._repository.list_all()
        cleaned = 0
        now = datetime.now()

        for node in all_nodes:
            if node.last_heartbeat is None:
                continue
            elapsed = (now - node.last_heartbeat).total_seconds()
            if elapsed > timeout_seconds and node.status != NodeStatus.OFFLINE:
                node.status = NodeStatus.OFFLINE
                node.is_available = False
                await self._repository.save(node)
                self._invalidate_cache(node.node_id)
                cleaned += 1
                logger.info(
                    "死亡节点已清理",
                    node_id=node.node_id,
                    offline_seconds=int(elapsed),
                )

        if cleaned > 0:
            logger.info("死亡节点清理完成", count=cleaned)
        return cleaned

    async def stop_node(self, node_id: str) -> dict:
        """
        停止指定节点（标记为 offline）

        Args:
            node_id: 节点 ID

        Returns:
            操作结果字典
        """
        await self._ensure_init()
        node = await self._repository.get_by_id(node_id)
        if node is None:
            return {
                "success": False,
                "node_id": node_id,
                "message": "节点不存在",
            }

        node.go_offline()
        await self._repository.save(node)
        self._invalidate_cache(node_id)

        logger.info("节点已停止", node_id=node_id)
        return {
            "success": True,
            "node_id": node_id,
            "message": "节点已停止",
            "node": self._node_to_cache_dict(node),
        }

    async def get_node(self, node_id: str) -> Optional[dict]:
        """获取单个节点信息（带心跳检查）"""
        await self._ensure_init()
        cached = await self._refresh_cache(node_id)
        if cached is None:
            return None
        return self._apply_heartbeat_check(cached)

    async def get_all_nodes(self) -> list[dict]:
        """获取所有节点信息（带心跳检查）"""
        await self._ensure_init()
        all_nodes = await self._repository.list_all()
        result = []
        for node in all_nodes:
            cached = self._node_to_cache_dict(node)
            with self._cache_lock:
                self._cache[node.node_id] = cached
            result.append(self._apply_heartbeat_check(cached))
        return result

    async def close(self) -> None:
        """关闭存储连接并清空缓存"""
        self._invalidate_cache()
        await self._repository.close()
        self._initialized = False
        logger.info("持久化节点存储已关闭")


__all__ = [
    "PersistentNodeStorage",
    "NodeRegistration",
    "NodeHeartbeat",
]

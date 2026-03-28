"""
节点实体模块

基于DDD设计原则的节点实体：
- 唯一标识：node_id
- 属性：status, capacity, tags
- 方法：状态判断、资源查询

使用示例：
    from src.core.entities import Node, NodeStatus

    node = Node(
        node_id="node_001",
        platform="windows"
    )
"""

import platform
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class NodeStatus(Enum):
    """节点状态枚举"""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    IDLE = "idle"
    UNKNOWN = "unknown"


class NodePlatform(Enum):
    """节点平台枚举"""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"


@dataclass
class Node:
    """
    节点实体

    代表系统中的计算节点，具有以下职责：
    - 管理节点基本信息和状态
    - 处理节点状态转换
    - 提供资源容量信息
    """
    node_id: str = field(default_factory=lambda: f"node_{uuid.uuid4().hex[:12]}")
    platform: str = field(default_factory=platform.system)
    status: NodeStatus = NodeStatus.OFFLINE
    capacity: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    owner: str = "unknown"
    registered_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    is_available: bool = False
    is_idle: bool = False

    @property
    def is_online(self) -> bool:
        """检查节点是否在线"""
        return self.status in [NodeStatus.ONLINE, NodeStatus.IDLE, NodeStatus.BUSY]

    @property
    def is_available_for_task(self) -> bool:
        """检查节点是否可用于新任务"""
        return self.is_online and self.is_idle

    def go_online(self) -> None:
        """节点上线"""
        self.status = NodeStatus.ONLINE
        self.last_heartbeat = datetime.now()

    def go_offline(self) -> None:
        """节点下线"""
        self.status = NodeStatus.OFFLINE
        self.is_available = False

    def set_busy(self) -> None:
        """设置节点忙碌"""
        self.status = NodeStatus.BUSY
        self.is_idle = False

    def set_idle(self) -> None:
        """设置节点空闲"""
        self.status = NodeStatus.IDLE
        self.is_idle = True

    def update_heartbeat(self) -> None:
        """更新心跳"""
        self.last_heartbeat = datetime.now()
        if self.status == NodeStatus.OFFLINE:
            self.go_online()

    def get_available_resources(self) -> dict[str, Any]:
        """获取可用资源"""
        if not self.is_online:
            return {}
        return self.capacity.copy()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "platform": self.platform,
            "status": self.status.value,
            "capacity": self.capacity,
            "tags": self.tags,
            "owner": self.owner,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "is_available": self.is_available,
            "is_idle": self.is_idle
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Node":
        """从字典创建节点实体"""
        return cls(
            node_id=data.get("node_id", ""),
            platform=data.get("platform", "unknown"),
            status=NodeStatus(data.get("status", "offline")),
            capacity=data.get("capacity", {}),
            tags=data.get("tags", {}),
            owner=data.get("owner", "unknown"),
            registered_at=datetime.fromisoformat(data["registered_at"]) if data.get("registered_at") else None,
            last_heartbeat=datetime.fromisoformat(data["last_heartbeat"]) if data.get("last_heartbeat") else None,
            is_available=data.get("is_available", False),
            is_idle=data.get("is_idle", False)
        )


class NodeFactory:
    """节点工厂类"""

    @staticmethod
    def create_local(
        cpu_limit: float,
        memory_limit: int,
        storage_limit: int,
        user_id: Optional[str] = None
    ) -> Node:
        """创建本地节点"""
        return Node(
            node_id=f"local_{uuid.uuid4().hex[:8]}",
            platform=platform.system(),
            status=NodeStatus.OFFLINE,
            capacity={
                "cpu_limit": cpu_limit,
                "memory_limit": memory_limit,
                "storage_limit": storage_limit
            },
            tags={"user_id": user_id or "unknown"},
            owner=user_id or "unknown"
        )

    @staticmethod
    def create_from_dict(data: dict[str, Any]) -> Node:
        """从字典创建节点"""
        return Node.from_dict(data)


__all__ = ["Node", "NodeStatus", "NodePlatform", "NodeFactory"]

"""
调度器数据模型

定义任务和节点的核心数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class TaskStatus(Enum):
    """任务状态枚举"""

    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETED = "deleted"


class NodeStatus(Enum):
    """节点状态枚举"""

    OFFLINE = "offline"
    ONLINE_IDLE = "online_idle"
    ONLINE_BUSY = "online_busy"
    ONLINE_UNAVAILABLE = "online_unavailable"


@dataclass
class Task:
    """任务数据模型"""

    task_id: str
    code: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    assigned_at: Optional[float] = None
    assigned_node: Optional[str] = None
    completed_at: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None
    required_resources: dict[str, Any] = field(default_factory=lambda: {"cpu": 1.0, "memory": 512})
    user_id: Optional[str] = None
    priority: int = 0
    timeout: int = 300

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "code": self.code,
            "status": self.status.value,
            "created_at": self.created_at,
            "assigned_at": self.assigned_at,
            "assigned_node": self.assigned_node,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "required_resources": self.required_resources,
            "user_id": self.user_id,
            "priority": self.priority,
            "timeout": self.timeout,
        }


@dataclass
class Node:
    """节点数据模型"""

    node_id: str
    capacity: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, Any] = field(default_factory=dict)
    registered_at: float = field(default_factory=lambda: datetime.now().timestamp())
    last_heartbeat: float = field(default_factory=lambda: datetime.now().timestamp())
    current_load: dict[str, Any] = field(
        default_factory=lambda: {"cpu_usage": 0.0, "memory_usage": 0}
    )
    available_resources: dict[str, Any] = field(default_factory=dict)
    is_idle: bool = True
    is_available: bool = True
    status: NodeStatus = NodeStatus.ONLINE_IDLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "capacity": self.capacity,
            "tags": self.tags,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "current_load": self.current_load,
            "available_resources": self.available_resources,
            "is_idle": self.is_idle,
            "is_available": self.is_available,
            "status": self.status.value,
        }

    def update_status(self) -> None:
        """根据当前状态更新节点状态枚举"""
        import time

        current_time = time.time()

        if current_time - self.last_heartbeat > 180:
            self.status = NodeStatus.OFFLINE
        elif not self.is_available:
            self.status = NodeStatus.ONLINE_UNAVAILABLE
        elif not self.is_idle:
            self.status = NodeStatus.ONLINE_BUSY
        else:
            self.status = NodeStatus.ONLINE_IDLE


__all__ = ["Task", "Node", "TaskStatus", "NodeStatus"]

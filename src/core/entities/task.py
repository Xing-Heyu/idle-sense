"""
任务实体模块

基于DDD设计原则的任务实体：
- 唯一标识：task_id
- 属性：code, status, resources, results
- 方法：状态转换、结果处理

使用示例：
    from src.core.entities import Task, TaskStatus

    task = Task(
        task_id="task_001",
        code="print('hello')",
        timeout=300
    )
"""

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(Enum):
    """任务类型枚举"""
    SINGLE_NODE = "single_node"
    DISTRIBUTED = "distributed"


@dataclass
class Task:
    """
    任务实体

    代表系统中提交的计算任务，具有以下职责：
    - 管理任务基本信息和状态
    - 处理任务状态转换
    - 记录任务执行结果
    """
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    code: str = ""
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    timeout: int = 300
    cpu_request: float = 1.0
    memory_request: int = 512
    task_type: TaskType = TaskType.SINGLE_NODE
    assigned_node: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    resources: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> Optional[float]:
        """获取任务执行时长（秒）"""
        if self.started_at:
            end_time = self.completed_at or datetime.now()
            return (end_time - self.started_at).total_seconds()
        return None

    @property
    def is_running(self) -> bool:
        """检查任务是否正在运行"""
        return self.status == TaskStatus.RUNNING

    @property
    def is_completed(self) -> bool:
        """检查任务是否已完成"""
        return self.status == TaskStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """检查任务是否失败"""
        return self.status == TaskStatus.FAILED

    @property
    def is_finished(self) -> bool:
        """检查任务是否结束（完成或失败）"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]

    def start(self, assigned_node: str) -> None:
        """开始执行任务"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()
        self.assigned_node = assigned_node

    def complete(self, result: str) -> None:
        """完成任务"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.result = result

    def fail(self, error: str) -> None:
        """任务失败"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.error = error

    def cancel(self) -> None:
        """取消任务"""
        if self.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            self.status = TaskStatus.CANCELLED
            self.completed_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "code": self.code,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "user_id": self.user_id,
            "timeout": self.timeout,
            "cpu_request": self.cpu_request,
            "memory_request": self.memory_request,
            "task_type": self.task_type.value,
            "assigned_node": self.assigned_node,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "duration": self.duration
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """从字典创建任务实体"""
        return cls(
            task_id=data.get("task_id", ""),
            code=data.get("code", ""),
            status=TaskStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            user_id=data.get("user_id"),
            timeout=data.get("timeout", 300),
            cpu_request=data.get("cpu_request", 1.0),
            memory_request=data.get("memory_request", 512),
            task_type=TaskType(data.get("task_type", "single_node")),
            assigned_node=data.get("assigned_node"),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            result=data.get("result"),
            error=data.get("error")
        )


class TaskFactory:
    """任务工厂类"""

    @staticmethod
    def create(
        code: str,
        user_id: Optional[str] = None,
        timeout: int = 300,
        cpu: float = 1.0,
        memory: int = 512,
        task_type: TaskType = TaskType.SINGLE_NODE
    ) -> Task:
        """创建新任务"""
        return Task(
            task_id=f"task_{hashlib.sha256(f'{time.time()}_{code[:50]}'.encode()).hexdigest()[:12]}",
            code=code,
            user_id=user_id,
            timeout=timeout,
            cpu_request=cpu,
            memory_request=memory,
            task_type=task_type,
            resources={"cpu": cpu, "memory": memory}
        )

    @staticmethod
    def create_from_dict(data: dict[str, Any]) -> Task:
        """从字典创建任务"""
        return Task.from_dict(data)


__all__ = ["Task", "TaskStatus", "TaskType", "TaskFactory"]

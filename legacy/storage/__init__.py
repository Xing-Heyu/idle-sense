"""
Storage backend abstraction layer.

This module provides a pluggable storage architecture inspired by Celery's
backend design, supporting multiple storage backends (Memory, Redis, SQLite).

Architecture Reference:
- Celery: https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend
- Redis: High-performance in-memory data store
- SQLite: Lightweight disk-based database
"""
import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETED = "deleted"


class NodeStatus(str, Enum):
    """Node status enumeration."""
    ONLINE_AVAILABLE = "online_available"
    ONLINE_BUSY = "online_busy"
    ONLINE_UNAVAILABLE = "online_unavailable"
    OFFLINE = "offline"


@dataclass
class TaskInfo:
    """Task information data class."""
    task_id: int
    code: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    assigned_at: Optional[float] = None
    assigned_node: Optional[str] = None
    completed_at: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None
    timeout: int = 300
    resources: dict[str, Any] = field(default_factory=lambda: {"cpu": 1.0, "memory": 512})
    user_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "code": self.code,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "created_at": self.created_at,
            "assigned_at": self.assigned_at,
            "assigned_node": self.assigned_node,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "timeout": self.timeout,
            "resources": self.resources,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskInfo":
        """Create from dictionary."""
        if isinstance(data.get("status"), str):
            data["status"] = TaskStatus(data["status"])
        return cls(**data)


@dataclass
class NodeInfo:
    """Node information data class."""
    node_id: str
    capacity: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, Any] = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: Optional[float] = None
    status: NodeStatus = NodeStatus.OFFLINE
    current_load: dict[str, Any] = field(default_factory=dict)
    is_idle: bool = False
    available_resources: dict[str, Any] = field(default_factory=dict)
    cpu_usage: float = 0.0
    memory_usage: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "capacity": self.capacity,
            "tags": self.tags,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "status": self.status.value if isinstance(self.status, NodeStatus) else self.status,
            "current_load": self.current_load,
            "is_idle": self.is_idle,
            "available_resources": self.available_resources,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeInfo":
        """Create from dictionary."""
        if isinstance(data.get("status"), str):
            data["status"] = NodeStatus(data["status"])
        return cls(**data)


@runtime_checkable
class StorageBackend(Protocol):
    """
    Storage backend protocol.

    This protocol defines the interface that all storage backends must implement.
    Inspired by Celery's backend architecture.
    """

    async def store_task(self, task: TaskInfo) -> None:
        """Store a task."""
        ...

    async def get_task(self, task_id: int) -> Optional[TaskInfo]:
        """Get a task by ID."""
        ...

    async def update_task(self, task_id: int, updates: dict[str, Any]) -> None:
        """Update a task."""
        ...

    async def delete_task(self, task_id: int) -> None:
        """Delete a task."""
        ...

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> list[TaskInfo]:
        """List tasks with optional filtering."""
        ...

    async def store_node(self, node: NodeInfo) -> None:
        """Store node information."""
        ...

    async def get_node(self, node_id: str) -> Optional[NodeInfo]:
        """Get node information."""
        ...

    async def update_node(self, node_id: str, updates: dict[str, Any]) -> None:
        """Update node information."""
        ...

    async def list_nodes(
        self,
        status: Optional[NodeStatus] = None
    ) -> list[NodeInfo]:
        """List nodes with optional filtering."""
        ...

    async def get_pending_task_for_node(self, node_id: str) -> Optional[TaskInfo]:
        """Get a pending task suitable for a node."""
        ...

    async def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        ...


class BaseStorage:  # noqa: B024
    """Base storage implementation with common utilities."""

    def __init__(self, task_ttl: int = 86400, result_ttl: int = 3600):
        self.task_ttl = task_ttl
        self.result_ttl = result_ttl

    def _serialize_task(self, task: TaskInfo) -> str:
        """Serialize task to JSON string."""
        return json.dumps(task.to_dict())

    def _deserialize_task(self, data: str) -> TaskInfo:
        """Deserialize task from JSON string."""
        return TaskInfo.from_dict(json.loads(data))

    def _serialize_node(self, node: NodeInfo) -> str:
        """Serialize node to JSON string."""
        return json.dumps(node.to_dict())

    def _deserialize_node(self, data: str) -> NodeInfo:
        """Deserialize node from JSON string."""
        return NodeInfo.from_dict(json.loads(data))

    def _calculate_match_score(
        self,
        node: NodeInfo,
        task: TaskInfo
    ) -> float:
        """
        Calculate task-node match score.

        Algorithm inspired by Kubernetes scheduler:
        - Resource fit (40%)
        - Load balance (30%)
        - Idle bonus (20%)
        - Affinity (10%)

        Returns 0 if resources are insufficient.
        """
        required_cpu = task.resources.get("cpu", 1.0)
        required_memory = task.resources.get("memory", 512)
        available_cpu = node.available_resources.get("cpu", 0)
        available_memory = node.available_resources.get("memory", 0)

        if available_cpu < required_cpu or available_memory < required_memory:
            return 0.0

        score = 0.0

        cpu_ratio = required_cpu / max(available_cpu, 0.1)
        score += min(cpu_ratio, 1.0) * 0.4

        mem_ratio = required_memory / max(available_memory, 1)
        score += min(mem_ratio, 1.0) * 0.3

        if node.is_idle:
            score += 0.2

        load_factor = 1.0 - min(node.cpu_usage / 100.0, 1.0)
        score += load_factor * 0.1

        return score


class MemoryStorage(BaseStorage):
    """
    In-memory storage backend.

    Suitable for development, testing, and single-node deployments.
    Data is lost on restart.

    Usage:
        storage = MemoryStorage()
        await storage.store_task(task)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tasks: dict[int, TaskInfo] = {}
        self._nodes: dict[str, NodeInfo] = {}
        self._task_counter: int = 0
        self._lock = asyncio.Lock()

    async def store_task(self, task: TaskInfo) -> None:
        async with self._lock:
            if task.task_id == 0:
                self._task_counter += 1
                task.task_id = self._task_counter
            self._tasks[task.task_id] = task

    async def get_task(self, task_id: int) -> Optional[TaskInfo]:
        return self._tasks.get(task_id)

    async def update_task(self, task_id: int, updates: dict[str, Any]) -> None:
        async with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                for key, value in updates.items():
                    if hasattr(task, key):
                        setattr(task, key, value)

    async def delete_task(self, task_id: int) -> None:
        async with self._lock:
            self._tasks.pop(task_id, None)

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> list[TaskInfo]:
        tasks = list(self._tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]
        if user_id:
            tasks = [t for t in tasks if t.user_id == user_id]

        return sorted(tasks, key=lambda t: t.created_at, reverse=True)[:limit]

    async def store_node(self, node: NodeInfo) -> None:
        async with self._lock:
            self._nodes[node.node_id] = node

    async def get_node(self, node_id: str) -> Optional[NodeInfo]:
        return self._nodes.get(node_id)

    async def update_node(self, node_id: str, updates: dict[str, Any]) -> None:
        async with self._lock:
            if node_id in self._nodes:
                node = self._nodes[node_id]
                for key, value in updates.items():
                    if hasattr(node, key):
                        setattr(node, key, value)

    async def list_nodes(
        self,
        status: Optional[NodeStatus] = None
    ) -> list[NodeInfo]:
        nodes = list(self._nodes.values())

        if status:
            nodes = [n for n in nodes if n.status == status]

        return nodes

    async def get_pending_task_for_node(self, node_id: str) -> Optional[TaskInfo]:
        node = await self.get_node(node_id)
        if not node:
            return None

        pending_tasks = [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]

        if not pending_tasks:
            return None

        best_task = None
        best_score = -1

        for task in pending_tasks:
            score = self._calculate_match_score(node, task)
            if score > best_score:
                best_score = score
                best_task = task

        if best_task and best_score > 0:
            best_task.status = TaskStatus.ASSIGNED
            best_task.assigned_node = node_id
            best_task.assigned_at = time.time()
            return best_task

        return None

    async def get_stats(self) -> dict[str, Any]:
        tasks = list(self._tasks.values())
        nodes = list(self._nodes.values())

        return {
            "total_tasks": len(tasks),
            "pending_tasks": len([t for t in tasks if t.status == TaskStatus.PENDING]),
            "running_tasks": len([t for t in tasks if t.status == TaskStatus.RUNNING]),
            "completed_tasks": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
            "failed_tasks": len([t for t in tasks if t.status == TaskStatus.FAILED]),
            "total_nodes": len(nodes),
            "available_nodes": len([n for n in nodes if n.status == NodeStatus.ONLINE_AVAILABLE]),
            "busy_nodes": len([n for n in nodes if n.status == NodeStatus.ONLINE_BUSY]),
            "offline_nodes": len([n for n in nodes if n.status == NodeStatus.OFFLINE]),
        }


class RedisStorage(BaseStorage):
    """
    Redis storage backend.

    Suitable for production multi-node deployments.
    Provides persistence and distributed access.

    Requirements:
        pip install redis

    Usage:
        storage = RedisStorage("redis://localhost:6379/0")
        await storage.store_task(task)

    Reference:
        https://redis.io/docs/data-types/
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "idle_accelerator:",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self._client = None
        self._task_counter_key = f"{key_prefix}task_counter"

    async def _get_client(self):
        """Get or create Redis client."""
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

    async def store_task(self, task: TaskInfo) -> None:
        client = await self._get_client()

        if task.task_id == 0:
            task.task_id = await client.incr(self._task_counter_key)

        key = f"{self.key_prefix}task:{task.task_id}"
        await client.setex(
            key,
            self.task_ttl,
            self._serialize_task(task)
        )
        await client.sadd(f"{self.key_prefix}tasks:pending", task.task_id)

    async def get_task(self, task_id: int) -> Optional[TaskInfo]:
        client = await self._get_client()
        key = f"{self.key_prefix}task:{task_id}"
        data = await client.get(key)

        if data:
            return self._deserialize_task(data.decode())
        return None

    async def update_task(self, task_id: int, updates: dict[str, Any]) -> None:
        task = await self.get_task(task_id)
        if task:
            for key, value in updates.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            await self.store_task(task)

    async def delete_task(self, task_id: int) -> None:
        client = await self._get_client()
        key = f"{self.key_prefix}task:{task_id}"
        await client.delete(key)
        await client.srem(f"{self.key_prefix}tasks:pending", task_id)

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> list[TaskInfo]:
        client = await self._get_client()

        pattern = f"{self.key_prefix}task:*"
        keys = []
        async for key in client.scan_iter(match=pattern):
            keys.append(key)

        tasks = []
        for key in keys[:limit * 2]:
            data = await client.get(key)
            if data:
                task = self._deserialize_task(data.decode())
                if status and task.status != status:
                    continue
                if user_id and task.user_id != user_id:
                    continue
                tasks.append(task)

        return sorted(tasks, key=lambda t: t.created_at, reverse=True)[:limit]

    async def store_node(self, node: NodeInfo) -> None:
        client = await self._get_client()
        key = f"{self.key_prefix}node:{node.node_id}"
        await client.set(key, self._serialize_node(node))

    async def get_node(self, node_id: str) -> Optional[NodeInfo]:
        client = await self._get_client()
        key = f"{self.key_prefix}node:{node_id}"
        data = await client.get(key)

        if data:
            return self._deserialize_node(data.decode())
        return None

    async def update_node(self, node_id: str, updates: dict[str, Any]) -> None:
        node = await self.get_node(node_id)
        if node:
            for key, value in updates.items():
                if hasattr(node, key):
                    setattr(node, key, value)
            await self.store_node(node)

    async def list_nodes(
        self,
        status: Optional[NodeStatus] = None
    ) -> list[NodeInfo]:
        client = await self._get_client()

        pattern = f"{self.key_prefix}node:*"
        nodes = []

        async for key in client.scan_iter(match=pattern):
            data = await client.get(key)
            if data:
                node = self._deserialize_node(data.decode())
                if status and node.status != status:
                    continue
                nodes.append(node)

        return nodes

    async def get_pending_task_for_node(self, node_id: str) -> Optional[TaskInfo]:
        node = await self.get_node(node_id)
        if not node:
            return None

        tasks = await self.list_tasks(status=TaskStatus.PENDING)

        if not tasks:
            return None

        best_task = None
        best_score = -1

        for task in tasks:
            score = self._calculate_match_score(node, task)
            if score > best_score:
                best_score = score
                best_task = task

        if best_task and best_score > 0:
            await self.update_task(best_task.task_id, {
                "status": TaskStatus.ASSIGNED,
                "assigned_node": node_id,
                "assigned_at": time.time()
            })
            return best_task

        return None

    async def get_stats(self) -> dict[str, Any]:
        tasks = await self.list_tasks(limit=10000)
        nodes = await self.list_nodes()

        return {
            "total_tasks": len(tasks),
            "pending_tasks": len([t for t in tasks if t.status == TaskStatus.PENDING]),
            "running_tasks": len([t for t in tasks if t.status == TaskStatus.RUNNING]),
            "completed_tasks": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
            "failed_tasks": len([t for t in tasks if t.status == TaskStatus.FAILED]),
            "total_nodes": len(nodes),
            "available_nodes": len([n for n in nodes if n.status == NodeStatus.ONLINE_AVAILABLE]),
            "busy_nodes": len([n for n in nodes if n.status == NodeStatus.ONLINE_BUSY]),
            "offline_nodes": len([n for n in nodes if n.status == NodeStatus.OFFLINE]),
        }


class SQLiteStorage(BaseStorage):
    """
    SQLite storage backend.

    Suitable for single-node production deployments.
    Provides persistence with zero external dependencies.

    Usage:
        storage = SQLiteStorage("data/scheduler.db")
        await storage.store_task(task)
    """

    def __init__(
        self,
        db_path: str = "data/scheduler.db",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.db_path = db_path
        self._conn = None

    async def _get_connection(self):
        """Get or create database connection."""
        if self._conn is None:
            import os

            import aiosqlite

            os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".", exist_ok=True)
            self._conn = await aiosqlite.connect(self.db_path)
            await self._init_tables()
        return self._conn

    async def _init_tables(self):
        """Initialize database tables."""
        conn = await self._get_connection()

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at REAL NOT NULL,
                assigned_at REAL,
                assigned_node TEXT,
                completed_at REAL,
                result TEXT,
                error TEXT,
                timeout INTEGER DEFAULT 300,
                resources TEXT,
                user_id TEXT
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                capacity TEXT,
                tags TEXT,
                registered_at REAL NOT NULL,
                last_heartbeat REAL,
                status TEXT NOT NULL DEFAULT 'offline',
                current_load TEXT,
                is_idle INTEGER DEFAULT 0,
                available_resources TEXT,
                cpu_usage REAL DEFAULT 0,
                memory_usage REAL DEFAULT 0
            )
        """)

        await conn.commit()

    async def store_task(self, task: TaskInfo) -> None:
        conn = await self._get_connection()

        cursor = await conn.execute(
            """
            INSERT INTO tasks (code, status, created_at, assigned_at, assigned_node,
                              completed_at, result, error, timeout, resources, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.code,
                task.status.value if isinstance(task.status, TaskStatus) else task.status,
                task.created_at,
                task.assigned_at,
                task.assigned_node,
                task.completed_at,
                task.result,
                task.error,
                task.timeout,
                json.dumps(task.resources),
                task.user_id
            )
        )
        await conn.commit()
        task.task_id = cursor.lastrowid

    async def get_task(self, task_id: int) -> Optional[TaskInfo]:
        conn = await self._get_connection()

        async with conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            return self._row_to_task(row)
        return None

    def _row_to_task(self, row) -> TaskInfo:
        """Convert database row to TaskInfo."""
        return TaskInfo(
            task_id=row[0],
            code=row[1],
            status=TaskStatus(row[2]),
            created_at=row[3],
            assigned_at=row[4],
            assigned_node=row[5],
            completed_at=row[6],
            result=row[7],
            error=row[8],
            timeout=row[9],
            resources=json.loads(row[10]) if row[10] else {},
            user_id=row[11]
        )

    async def update_task(self, task_id: int, updates: dict[str, Any]) -> None:
        conn = await self._get_connection()

        _TASK_ALLOWED_COLUMNS = {
            "status", "result", "error", "assigned_node", "resources",
            "started_at", "completed_at", "progress", "priority",
        }
        set_clauses = []
        values = []
        for key, value in updates.items():
            if key not in _TASK_ALLOWED_COLUMNS:
                continue
            if key == "resources":
                value = json.dumps(value)
            elif key == "status" and isinstance(value, TaskStatus):
                value = value.value
            set_clauses.append(f"{key} = ?")
            values.append(value)

        values.append(task_id)

        await conn.execute(
            f"UPDATE tasks SET {', '.join(set_clauses)} WHERE task_id = ?",
            values
        )
        await conn.commit()

    async def delete_task(self, task_id: int) -> None:
        conn = await self._get_connection()
        await conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        await conn.commit()

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> list[TaskInfo]:
        conn = await self._get_connection()

        query = "SELECT * FROM tasks WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status.value)
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        return [self._row_to_task(row) for row in rows]

    async def store_node(self, node: NodeInfo) -> None:
        conn = await self._get_connection()

        await conn.execute(
            """
            INSERT OR REPLACE INTO nodes
            (node_id, capacity, tags, registered_at, last_heartbeat, status,
             current_load, is_idle, available_resources, cpu_usage, memory_usage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node.node_id,
                json.dumps(node.capacity),
                json.dumps(node.tags),
                node.registered_at,
                node.last_heartbeat,
                node.status.value if isinstance(node.status, NodeStatus) else node.status,
                json.dumps(node.current_load),
                1 if node.is_idle else 0,
                json.dumps(node.available_resources),
                node.cpu_usage,
                node.memory_usage
            )
        )
        await conn.commit()

    async def get_node(self, node_id: str) -> Optional[NodeInfo]:
        conn = await self._get_connection()

        async with conn.execute(
            "SELECT * FROM nodes WHERE node_id = ?", (node_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            return self._row_to_node(row)
        return None

    def _row_to_node(self, row) -> NodeInfo:
        """Convert database row to NodeInfo."""
        return NodeInfo(
            node_id=row[0],
            capacity=json.loads(row[1]) if row[1] else {},
            tags=json.loads(row[2]) if row[2] else {},
            registered_at=row[3],
            last_heartbeat=row[4],
            status=NodeStatus(row[5]),
            current_load=json.loads(row[6]) if row[6] else {},
            is_idle=bool(row[7]),
            available_resources=json.loads(row[8]) if row[8] else {},
            cpu_usage=row[9],
            memory_usage=row[10]
        )

    async def update_node(self, node_id: str, updates: dict[str, Any]) -> None:
        conn = await self._get_connection()

        _NODE_ALLOWED_COLUMNS = {
            "status", "capacity", "tags", "current_load", "available_resources",
            "is_idle", "last_heartbeat", "completed_tasks",
        }
        set_clauses = []
        values = []
        for key, value in updates.items():
            if key not in _NODE_ALLOWED_COLUMNS:
                continue
            if key in ("capacity", "tags", "current_load", "available_resources"):
                value = json.dumps(value)
            elif key == "status" and isinstance(value, NodeStatus):
                value = value.value
            elif key == "is_idle":
                value = 1 if value else 0
            set_clauses.append(f"{key} = ?")
            values.append(value)

        values.append(node_id)

        await conn.execute(
            f"UPDATE nodes SET {', '.join(set_clauses)} WHERE node_id = ?",
            values
        )
        await conn.commit()

    async def list_nodes(
        self,
        status: Optional[NodeStatus] = None
    ) -> list[NodeInfo]:
        conn = await self._get_connection()

        query = "SELECT * FROM nodes WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status.value)

        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        return [self._row_to_node(row) for row in rows]

    async def get_pending_task_for_node(self, node_id: str) -> Optional[TaskInfo]:
        node = await self.get_node(node_id)
        if not node:
            return None

        tasks = await self.list_tasks(status=TaskStatus.PENDING)

        if not tasks:
            return None

        best_task = None
        best_score = -1

        for task in tasks:
            score = self._calculate_match_score(node, task)
            if score > best_score:
                best_score = score
                best_task = task

        if best_task and best_score > 0:
            await self.update_task(best_task.task_id, {
                "status": TaskStatus.ASSIGNED,
                "assigned_node": node_id,
                "assigned_at": time.time()
            })
            return best_task

        return None

    async def get_stats(self) -> dict[str, Any]:
        tasks = await self.list_tasks(limit=10000)
        nodes = await self.list_nodes()

        return {
            "total_tasks": len(tasks),
            "pending_tasks": len([t for t in tasks if t.status == TaskStatus.PENDING]),
            "running_tasks": len([t for t in tasks if t.status == TaskStatus.RUNNING]),
            "completed_tasks": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
            "failed_tasks": len([t for t in tasks if t.status == TaskStatus.FAILED]),
            "total_nodes": len(nodes),
            "available_nodes": len([n for n in nodes if n.status == NodeStatus.ONLINE_AVAILABLE]),
            "busy_nodes": len([n for n in nodes if n.status == NodeStatus.ONLINE_BUSY]),
            "offline_nodes": len([n for n in nodes if n.status == NodeStatus.OFFLINE]),
        }


def create_storage(
    backend: str = "memory",
    **kwargs
) -> StorageBackend:
    """
    Factory function to create storage backend.

    Args:
        backend: Storage backend type ('memory', 'redis', 'sqlite')
        **kwargs: Backend-specific configuration

    Returns:
        StorageBackend instance

    Examples:
        # Memory storage (default)
        storage = create_storage()

        # Redis storage
        storage = create_storage("redis", redis_url="redis://localhost:6379/0")

        # SQLite storage
        storage = create_storage("sqlite", db_path="data/scheduler.db")
    """
    backends = {
        "memory": MemoryStorage,
        "redis": RedisStorage,
        "sqlite": SQLiteStorage,
    }

    if backend not in backends:
        raise ValueError(
            f"Unknown storage backend: {backend}. "
            f"Available: {list(backends.keys())}"
        )

    return backends[backend](**kwargs)

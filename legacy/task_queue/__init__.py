"""Task Queue - High-performance task queue with multiple backends."""

from __future__ import annotations

import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    TIMEOUT = "timeout"


class TaskPriority(int, Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class Task(Generic[T]):
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    payload: Any = None
    priority: int = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: T | None = None
    error: str | None = None
    retries: int = 0
    max_retries: int = 3
    timeout_seconds: float = 300.0
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    @property
    def wait_time(self) -> float:
        if self.started_at:
            return self.started_at - self.created_at
        return time.time() - self.created_at

    @property
    def execution_time(self) -> float:
        if self.started_at:
            if self.completed_at:
                return self.completed_at - self.started_at
            return time.time() - self.started_at
        return 0.0

    @property
    def total_time(self) -> float:
        if self.completed_at:
            return self.completed_at - self.created_at
        return time.time() - self.created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "wait_time": round(self.wait_time, 3),
            "execution_time": round(self.execution_time, 3),
            "retries": self.retries,
            "error": self.error,
            "tags": self.tags,
        }


@dataclass
class QueueStats:
    total_enqueued: int = 0
    total_dequeued: int = 0
    total_completed: int = 0
    total_failed: int = 0
    current_size: int = 0
    pending_size: int = 0
    running_size: int = 0
    avg_wait_time_ms: float = 0.0
    avg_execution_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_enqueued": self.total_enqueued,
            "total_dequeued": self.total_dequeued,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "current_size": self.current_size,
            "pending_size": self.pending_size,
            "running_size": self.running_size,
            "avg_wait_time_ms": round(self.avg_wait_time_ms, 3),
            "avg_execution_time_ms": round(self.avg_execution_time_ms, 3),
        }


class TaskQueueBackend(ABC):
    @abstractmethod
    def enqueue(self, task: Task) -> bool:
        pass

    @abstractmethod
    def dequeue(self, timeout: float = 0) -> Task | None:
        pass

    @abstractmethod
    def peek(self) -> Task | None:
        pass

    @abstractmethod
    def size(self) -> int:
        pass

    @abstractmethod
    def clear(self) -> int:
        pass

    @abstractmethod
    def get_task(self, task_id: str) -> Task | None:
        pass

    @abstractmethod
    def update_task(self, task: Task) -> bool:
        pass


class MemoryQueueBackend(TaskQueueBackend):
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._queue: list[Task] = []
        self._tasks: dict[str, Task] = {}
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)

    def enqueue(self, task: Task) -> bool:
        with self._lock:
            if len(self._queue) >= self.max_size:
                return False

            task.status = TaskStatus.QUEUED
            self._queue.append(task)
            self._tasks[task.id] = task
            self._queue.sort(key=lambda t: t.priority, reverse=True)
            self._condition.notify()
            return True

    def dequeue(self, timeout: float = 0) -> Task | None:
        with self._condition:
            if not self._queue:
                if timeout > 0:
                    self._condition.wait(timeout)
                if not self._queue:
                    return None

            if self._queue:
                task = self._queue.pop(0)
                task.status = TaskStatus.RUNNING
                task.started_at = time.time()
                return task
            return None

    def peek(self) -> Task | None:
        with self._lock:
            return self._queue[0] if self._queue else None

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def clear(self) -> int:
        with self._lock:
            count = len(self._queue)
            self._queue.clear()
            return count

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def update_task(self, task: Task) -> bool:
        with self._lock:
            if task.id in self._tasks:
                self._tasks[task.id] = task
                return True
            return False


class RedisQueueBackend(TaskQueueBackend):
    def __init__(
        self,
        queue_name: str = "task_queue",
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
    ):
        self.queue_name = queue_name
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self._client = None
        self._task_prefix = f"{queue_name}:task:"

    @property
    def client(self):
        if self._client is None:
            try:
                import redis

                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    decode_responses=True,
                )
            except ImportError as e:
                raise ImportError("Redis support requires redis package") from e
        return self._client

    def _task_key(self, task_id: str) -> str:
        return f"{self._task_prefix}{task_id}"

    def enqueue(self, task: Task) -> bool:
        import json as json_module

        task.status = TaskStatus.QUEUED
        task_data = json_module.dumps(
            {
                "id": task.id,
                "name": task.name,
                "priority": task.priority,
                "payload": task.payload,
                "status": task.status.value,
                "created_at": task.created_at,
                "timeout_seconds": task.timeout_seconds,
                "max_retries": task.max_retries,
                "metadata": task.metadata,
                "tags": task.tags,
            }
        )

        self.client.hset(self._task_key(task.id), "data", task_data)
        self.client.zadd(self.queue_name, {task.id: -task.priority})

        return True

    def dequeue(self, timeout: float = 0) -> Task | None:
        import json as json_module

        result = self.client.zpopmax(self.queue_name)

        if not result:
            return None

        task_id, _ = result[0]
        task_data = self.client.hget(self._task_key(task_id), "data")

        if not task_data:
            return None

        data = json_module.loads(task_data)
        task = Task(
            id=data["id"],
            name=data["name"],
            priority=data["priority"],
            payload=data.get("payload"),
            status=TaskStatus.RUNNING,
            created_at=data["created_at"],
            started_at=time.time(),
            timeout_seconds=data.get("timeout_seconds", 300),
            max_retries=data.get("max_retries", 3),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
        )

        self.client.hset(
            self._task_key(task.id),
            "data",
            json_module.dumps({**data, "status": task.status.value, "started_at": task.started_at}),
        )

        return task

    def peek(self) -> Task | None:
        result = self.client.zrange(self.queue_name, -1, -1, withscores=True)

        if not result:
            return None

        task_id = result[0][0]
        return self.get_task(task_id)

    def size(self) -> int:
        return self.client.zcard(self.queue_name)

    def clear(self) -> int:
        count = self.size()
        task_ids = self.client.zrange(self.queue_name, 0, -1)

        if task_ids:
            for task_id in task_ids:
                self.client.delete(self._task_key(task_id))
            self.client.delete(self.queue_name)

        return count

    def get_task(self, task_id: str) -> Task | None:
        import json as json_module

        task_data = self.client.hget(self._task_key(task_id), "data")

        if not task_data:
            return None

        data = json_module.loads(task_data)
        return Task(
            id=data["id"],
            name=data["name"],
            priority=data["priority"],
            payload=data.get("payload"),
            status=TaskStatus(data["status"]),
            created_at=data["created_at"],
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            result=data.get("result"),
            error=data.get("error"),
            retries=data.get("retries", 0),
            max_retries=data.get("max_retries", 3),
            timeout_seconds=data.get("timeout_seconds", 300),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
        )

    def update_task(self, task: Task) -> bool:
        import json as json_module

        if not self.client.exists(self._task_key(task.id)):
            return False

        task_data = json_module.dumps(
            {
                "id": task.id,
                "name": task.name,
                "priority": task.priority,
                "payload": task.payload,
                "status": task.status.value,
                "created_at": task.created_at,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
                "result": task.result,
                "error": task.error,
                "retries": task.retries,
                "max_retries": task.max_retries,
                "timeout_seconds": task.timeout_seconds,
                "metadata": task.metadata,
                "tags": task.tags,
            }
        )

        self.client.hset(self._task_key(task.id), "data", task_data)
        return True


class TaskQueue(Generic[T]):
    def __init__(
        self,
        backend: TaskQueueBackend | None = None,
        max_workers: int = 4,
        default_timeout: float = 300.0,
    ):
        self.backend = backend or MemoryQueueBackend()
        self.max_workers = max_workers
        self.default_timeout = default_timeout

        self._stats = QueueStats()
        self._wait_times: list[float] = []
        self._execution_times: list[float] = []
        self._running_tasks: dict[str, Task] = {}
        self._handlers: dict[str, Callable] = {}
        self._workers: list[threading.Thread] = []
        self._running = False
        self._lock = threading.RLock()

    def register_handler(self, task_name: str, handler: Callable):
        self._handlers[task_name] = handler

    def unregister_handler(self, task_name: str):
        self._handlers.pop(task_name, None)

    def enqueue(
        self,
        name: str,
        payload: Any = None,
        priority: int = TaskPriority.NORMAL,
        timeout: float | None = None,
        max_retries: int = 3,
        metadata: dict | None = None,
        tags: list[str] | None = None,
    ) -> Task:
        task = Task(
            name=name,
            payload=payload,
            priority=priority,
            timeout_seconds=timeout or self.default_timeout,
            max_retries=max_retries,
            metadata=metadata or {},
            tags=tags or [],
        )

        if self.backend.enqueue(task):
            with self._lock:
                self._stats.total_enqueued += 1
                self._stats.current_size = self.backend.size()

        return task

    def dequeue(self, timeout: float = 0) -> Task | None:
        task = self.backend.dequeue(timeout)

        if task:
            with self._lock:
                self._stats.total_dequeued += 1
                self._stats.current_size = self.backend.size()
                self._running_tasks[task.id] = task
                self._wait_times.append(task.wait_time)
                if len(self._wait_times) > 100:
                    self._wait_times = self._wait_times[-100:]
                self._stats.avg_wait_time_ms = sum(self._wait_times) / len(self._wait_times) * 1000

        return task

    def complete(self, task: Task, result: Any = None):
        task.status = TaskStatus.COMPLETED
        task.result = result
        task.completed_at = time.time()

        with self._lock:
            self._stats.total_completed += 1
            self._running_tasks.pop(task.id, None)
            self._execution_times.append(task.execution_time)
            if len(self._execution_times) > 100:
                self._execution_times = self._execution_times[-100:]
            self._stats.avg_execution_time_ms = (
                sum(self._execution_times) / len(self._execution_times) * 1000
            )

        self.backend.update_task(task)

    def fail(self, task: Task, error: str):
        task.error = error

        if task.retries < task.max_retries:
            task.status = TaskStatus.RETRYING
            task.retries += 1
            self.backend.enqueue(task)
        else:
            task.status = TaskStatus.FAILED
            task.completed_at = time.time()
            with self._lock:
                self._stats.total_failed += 1
                self._running_tasks.pop(task.id, None)

        self.backend.update_task(task)

    def get_task(self, task_id: str) -> Task | None:
        task = self._running_tasks.get(task_id)
        if task:
            return task
        return self.backend.get_task(task_id)

    def cancel(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if task and task.status in (TaskStatus.PENDING, TaskStatus.QUEUED):
            task.status = TaskStatus.CANCELLED
            self.backend.update_task(task)
            return True
        return False

    def get_stats(self) -> QueueStats:
        with self._lock:
            self._stats.pending_size = self.backend.size()
            self._stats.running_size = len(self._running_tasks)
            return QueueStats(**dict(self._stats.__dict__.items()))

    def start_workers(self):
        if self._running:
            return

        self._running = True

        for _i in range(self.max_workers):
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            worker.start()
            self._workers.append(worker)

    def stop_workers(self, wait: bool = True):
        self._running = False

        if wait:
            for worker in self._workers:
                worker.join(timeout=5)

        self._workers.clear()

    def _worker_loop(self):
        while self._running:
            try:
                task = self.dequeue(timeout=1.0)

                if not task:
                    continue

                handler = self._handlers.get(task.name)

                if not handler:
                    self.fail(task, f"No handler registered for task: {task.name}")
                    continue

                try:
                    result = handler(task.payload)
                    self.complete(task, result)
                except Exception as e:
                    self.fail(task, str(e))

            except Exception:
                time.sleep(0.1)

    def clear(self) -> int:
        return self.backend.clear()


__all__ = [
    "TaskStatus",
    "TaskPriority",
    "Task",
    "QueueStats",
    "TaskQueueBackend",
    "MemoryQueueBackend",
    "RedisQueueBackend",
    "TaskQueue",
]

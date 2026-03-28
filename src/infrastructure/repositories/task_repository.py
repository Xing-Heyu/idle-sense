"""
任务仓储实现

基于内存的任务存储（实际项目中可能需要持久化）
"""

import threading
from typing import Optional

from src.core.entities import Task, TaskStatus
from src.core.interfaces.repositories import ITaskRepository


class InMemoryTaskRepository(ITaskRepository):
    """基于内存的任务仓储实现"""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = threading.RLock()

    def get_by_id(self, task_id: str) -> Optional[Task]:
        with self._lock:
            return self._tasks.get(task_id)

    def save(self, task: Task) -> Task:
        with self._lock:
            self._tasks[task.task_id] = task
            return task

    def update(self, task: Task) -> Task:
        with self._lock:
            if task.task_id in self._tasks:
                self._tasks[task.task_id] = task
            return task

    def delete(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False

    def list_by_user(self, user_id: str, limit: int = 100) -> list[Task]:
        with self._lock:
            user_tasks = [t for t in self._tasks.values() if t.user_id == user_id]
            return user_tasks[:limit]

    def list_by_status(self, status: TaskStatus, limit: int = 100) -> list[Task]:
        with self._lock:
            status_tasks = [t for t in self._tasks.values() if t.status == status]
            return status_tasks[:limit]

    def list_all(self, limit: int = 100) -> list[Task]:
        with self._lock:
            return list(self._tasks.values())[:limit]


__all__ = ["InMemoryTaskRepository"]

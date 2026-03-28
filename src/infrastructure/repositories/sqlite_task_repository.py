"""
SQLite任务仓储实现

提供基于SQLite的任务持久化存储
"""

import json
import os
from datetime import datetime
from typing import Optional

import aiosqlite

from src.core.entities import Task, TaskStatus, TaskType
from src.core.interfaces.repositories import ITaskRepository


class SQLiteTaskRepository(ITaskRepository):
    """
    基于SQLite的任务仓储实现

    提供任务数据的持久化存储，支持：
    - 自动创建数据库表
    - 异步IO操作
    - JSON序列化复杂字段
    """

    def __init__(self, db_path: str = "data/idle_sense.db"):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def _get_connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".", exist_ok=True)
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
            await self._init_tables()
        return self._conn

    async def _init_tables(self) -> None:
        conn = await self._get_connection()
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                code TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT,
                user_id TEXT,
                timeout INTEGER DEFAULT 300,
                cpu_request REAL DEFAULT 1.0,
                memory_request INTEGER DEFAULT 512,
                task_type TEXT DEFAULT 'single_node',
                assigned_node TEXT,
                started_at TEXT,
                completed_at TEXT,
                result TEXT,
                error TEXT,
                resources TEXT
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at)
        """)
        await conn.commit()

    def _row_to_task(self, row: aiosqlite.Row) -> Task:
        return Task(
            task_id=row["task_id"],
            code=row["code"],
            status=TaskStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
            user_id=row["user_id"],
            timeout=row["timeout"],
            cpu_request=row["cpu_request"],
            memory_request=row["memory_request"],
            task_type=TaskType(row["task_type"]) if row["task_type"] else TaskType.SINGLE_NODE,
            assigned_node=row["assigned_node"],
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            result=row["result"],
            error=row["error"],
            resources=json.loads(row["resources"]) if row["resources"] else {}
        )

    async def get_by_id(self, task_id: str) -> Optional[Task]:
        conn = await self._get_connection()
        async with conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)) as cursor:
            row = await cursor.fetchone()
        return self._row_to_task(row) if row else None

    async def save(self, task: Task) -> Task:
        conn = await self._get_connection()
        await conn.execute(
            """
            INSERT OR REPLACE INTO tasks
            (task_id, code, status, created_at, user_id, timeout, cpu_request, memory_request,
             task_type, assigned_node, started_at, completed_at, result, error, resources)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.task_id,
                task.code,
                task.status.value,
                task.created_at.isoformat() if task.created_at else None,
                task.user_id,
                task.timeout,
                task.cpu_request,
                task.memory_request,
                task.task_type.value,
                task.assigned_node,
                task.started_at.isoformat() if task.started_at else None,
                task.completed_at.isoformat() if task.completed_at else None,
                task.result,
                task.error,
                json.dumps(task.resources)
            )
        )
        await conn.commit()
        return task

    async def update(self, task: Task) -> Task:
        return await self.save(task)

    async def delete(self, task_id: str) -> bool:
        conn = await self._get_connection()
        cursor = await conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        await conn.commit()
        return cursor.rowcount > 0

    async def list_by_user(self, user_id: str, limit: int = 100) -> list[Task]:
        conn = await self._get_connection()
        async with conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_task(row) for row in rows]

    async def list_by_status(self, status: TaskStatus, limit: int = 100) -> list[Task]:
        conn = await self._get_connection()
        async with conn.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status.value, limit)
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_task(row) for row in rows]

    async def list_all(self, limit: int = 100) -> list[Task]:
        conn = await self._get_connection()
        async with conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_task(row) for row in rows]

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None


__all__ = ["SQLiteTaskRepository"]

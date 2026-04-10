"""
SQLite任务仓储实现

提供基于SQLite的任务持久化存储，使用连接池管理数据库连接
"""

import json
from datetime import datetime
from typing import Optional

import aiosqlite

from src.core.entities import Task, TaskStatus, TaskType
from src.core.interfaces.repositories import ITaskRepository
from src.infrastructure.repositories.sqlite_base import SQLiteConnectionPool


class SQLiteTaskRepository(ITaskRepository):
    """
    基于SQLite的任务仓储实现（使用连接池）

    提供任务数据的持久化存储，支持：
    - 自动创建数据库表
    - 异步IO操作
    - JSON序列化复杂字段
    - 连接池管理（解决并发问题）
    """

    def __init__(self, db_path: str = "data/idle_sense.db", pool_size: int = 5):
        self.db_path = db_path
        self._pool: Optional[SQLiteConnectionPool] = None
        self._pool_size = pool_size

    async def _get_pool(self) -> SQLiteConnectionPool:
        """获取或初始化连接池"""
        if self._pool is None:
            self._pool = SQLiteConnectionPool(
                db_path=self.db_path,
                max_connections=self._pool_size,
            )
            await self._pool.initialize()
            await self._init_tables()
        return self._pool

    async def _init_tables(self) -> None:
        """初始化数据库表结构"""
        if self._pool is None:
            return

        conn = await self._pool.get_connection()
        try:
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
        finally:
            await self._pool.release_connection(conn)

    def _row_to_task(self, row: aiosqlite.Row) -> Task:
        return Task(
            task_id=row["task_id"],
            code=row["code"],
            status=TaskStatus(row["status"]),
            created_at=(
                datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now()
            ),
            user_id=row["user_id"],
            timeout=row["timeout"],
            cpu_request=row["cpu_request"],
            memory_request=row["memory_request"],
            task_type=TaskType(row["task_type"]) if row["task_type"] else TaskType.SINGLE_NODE,
            assigned_node=row["assigned_node"],
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=(
                datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
            ),
            result=row["result"],
            error=row["error"],
            resources=json.loads(row["resources"]) if row["resources"] else {},
        )

    async def get_by_id(self, task_id: str) -> Optional[Task]:
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            async with conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)) as cursor:
                row = await cursor.fetchone()
            return self._row_to_task(row) if row else None
        finally:
            await pool.release_connection(conn)

    async def save(self, task: Task) -> Task:
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
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
                    json.dumps(task.resources),
                ),
            )
            await conn.commit()
            return task
        finally:
            await pool.release_connection(conn)

    async def update(self, task: Task) -> Task:
        return await self.save(task)

    async def delete(self, task_id: str) -> bool:
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            cursor = await conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await pool.release_connection(conn)

    async def list_by_user(self, user_id: str, limit: int = 100) -> list[Task]:
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            async with conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
            return [self._row_to_task(row) for row in rows]
        finally:
            await pool.release_connection(conn)

    async def list_by_status(self, status: TaskStatus, limit: int = 100) -> list[Task]:
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            async with conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status.value, limit),
            ) as cursor:
                rows = await cursor.fetchall()
            return [self._row_to_task(row) for row in rows]
        finally:
            await pool.release_connection(conn)

    async def list_all(self, limit: int = 100) -> list[Task]:
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            async with conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
            return [self._row_to_task(row) for row in rows]
        finally:
            await pool.release_connection(conn)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None


__all__ = ["SQLiteTaskRepository"]

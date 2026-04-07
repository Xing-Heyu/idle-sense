"""
SQLite节点仓储实现

提供基于SQLite的节点持久化存储，使用连接池管理数据库连接
"""

import json
from datetime import datetime
from typing import Optional

import aiosqlite

from src.core.entities import Node, NodeStatus
from src.core.interfaces.repositories import INodeRepository
from src.infrastructure.repositories.sqlite_base import SQLiteConnectionPool


class SQLiteNodeRepository(INodeRepository):
    """
    基于SQLite的节点仓储实现（使用连接池）

    提供节点数据的持久化存储，支持：
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
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL DEFAULT 'unknown',
                    status TEXT NOT NULL DEFAULT 'offline',
                    capacity TEXT,
                    tags TEXT,
                    owner TEXT DEFAULT 'unknown',
                    registered_at TEXT,
                    last_heartbeat TEXT,
                    is_available INTEGER DEFAULT 0,
                    is_idle INTEGER DEFAULT 0
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_nodes_owner ON nodes(owner)
            """)
            await conn.commit()
        finally:
            await self._pool.release_connection(conn)

    def _row_to_node(self, row: aiosqlite.Row) -> Node:
        return Node(
            node_id=row["node_id"],
            platform=row["platform"],
            status=NodeStatus(row["status"]),
            capacity=json.loads(row["capacity"]) if row["capacity"] else {},
            tags=json.loads(row["tags"]) if row["tags"] else {},
            owner=row["owner"],
            registered_at=datetime.fromisoformat(row["registered_at"]) if row["registered_at"] else None,
            last_heartbeat=datetime.fromisoformat(row["last_heartbeat"]) if row["last_heartbeat"] else None,
            is_available=bool(row["is_available"]),
            is_idle=bool(row["is_idle"])
        )

    async def get_by_id(self, node_id: str) -> Optional[Node]:
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            async with conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)) as cursor:
                row = await cursor.fetchone()
            return self._row_to_node(row) if row else None
        finally:
            await pool.release_connection(conn)

    async def save(self, node: Node) -> Node:
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            await conn.execute(
                """
                INSERT OR REPLACE INTO nodes
                (node_id, platform, status, capacity, tags, owner, registered_at, last_heartbeat, is_available, is_idle)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.node_id,
                    node.platform,
                    node.status.value,
                    json.dumps(node.capacity),
                    json.dumps(node.tags),
                    node.owner,
                    node.registered_at.isoformat() if node.registered_at else None,
                    node.last_heartbeat.isoformat() if node.last_heartbeat else None,
                    1 if node.is_available else 0,
                    1 if node.is_idle else 0
                )
            )
            await conn.commit()
            return node
        finally:
            await pool.release_connection(conn)

    async def update(self, node: Node) -> Node:
        return await self.save(node)

    async def delete(self, node_id: str) -> bool:
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            cursor = await conn.execute("DELETE FROM nodes WHERE node_id = ?", (node_id,))
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await pool.release_connection(conn)

    def _validate_pagination(self, limit: int, offset: int) -> tuple[int, int]:
        if limit <= 0:
            raise ValueError(f"limit must be > 0, got {limit}")
        if offset < 0:
            raise ValueError(f"offset must be >= 0, got {offset}")
        return min(limit, 1000), offset

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Node]:
        limit, offset = self._validate_pagination(limit, offset)
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            async with conn.execute(
                "SELECT * FROM nodes ORDER BY registered_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
            return [self._row_to_node(row) for row in rows]
        finally:
            await pool.release_connection(conn)

    async def list_by_status(self, status: NodeStatus, limit: int = 100, offset: int = 0) -> list[Node]:
        limit, offset = self._validate_pagination(limit, offset)
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            async with conn.execute(
                "SELECT * FROM nodes WHERE status = ? LIMIT ? OFFSET ?",
                (status.value, limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
            return [self._row_to_node(row) for row in rows]
        finally:
            await pool.release_connection(conn)

    async def list_online(self, limit: int = 100, offset: int = 0) -> list[Node]:
        limit, offset = self._validate_pagination(limit, offset)
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            async with conn.execute(
                "SELECT * FROM nodes WHERE status IN (?, ?, ?) LIMIT ? OFFSET ?",
                (NodeStatus.ONLINE.value, NodeStatus.IDLE.value, NodeStatus.BUSY.value, limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
            return [self._row_to_node(row) for row in rows]
        finally:
            await pool.release_connection(conn)

    async def list_idle(self, limit: int = 100, offset: int = 0) -> list[Node]:
        limit, offset = self._validate_pagination(limit, offset)
        pool = await self._get_pool()
        conn = await pool.get_connection()
        try:
            async with conn.execute(
                "SELECT * FROM nodes WHERE is_idle = 1 LIMIT ? OFFSET ?",
                (limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
            return [self._row_to_node(row) for row in rows]
        finally:
            await pool.release_connection(conn)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None


__all__ = ["SQLiteNodeRepository"]

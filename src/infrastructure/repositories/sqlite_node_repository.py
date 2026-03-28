"""
SQLite节点仓储实现

提供基于SQLite的节点持久化存储
"""

import json
import os
from datetime import datetime
from typing import Optional

import aiosqlite

from src.core.entities import Node, NodeStatus
from src.core.interfaces.repositories import INodeRepository


class SQLiteNodeRepository(INodeRepository):
    """
    基于SQLite的节点仓储实现

    提供节点数据的持久化存储，支持：
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
        conn = await self._get_connection()
        async with conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)) as cursor:
            row = await cursor.fetchone()
        return self._row_to_node(row) if row else None

    async def save(self, node: Node) -> Node:
        conn = await self._get_connection()
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

    async def update(self, node: Node) -> Node:
        return await self.save(node)

    async def delete(self, node_id: str) -> bool:
        conn = await self._get_connection()
        cursor = await conn.execute("DELETE FROM nodes WHERE node_id = ?", (node_id,))
        await conn.commit()
        return cursor.rowcount > 0

    async def list_all(self) -> list[Node]:
        conn = await self._get_connection()
        async with conn.execute("SELECT * FROM nodes ORDER BY registered_at DESC") as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_node(row) for row in rows]

    async def list_by_status(self, status: NodeStatus) -> list[Node]:
        conn = await self._get_connection()
        async with conn.execute("SELECT * FROM nodes WHERE status = ?", (status.value,)) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_node(row) for row in rows]

    async def list_online(self) -> list[Node]:
        conn = await self._get_connection()
        async with conn.execute(
            "SELECT * FROM nodes WHERE status IN (?, ?, ?)",
            (NodeStatus.ONLINE.value, NodeStatus.IDLE.value, NodeStatus.BUSY.value)
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_node(row) for row in rows]

    async def list_idle(self) -> list[Node]:
        conn = await self._get_connection()
        async with conn.execute("SELECT * FROM nodes WHERE is_idle = 1") as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_node(row) for row in rows]

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None


__all__ = ["SQLiteNodeRepository"]

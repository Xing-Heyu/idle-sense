"""
SQLite 连接池实现

提供基于 aiosqlite 的异步连接池，支持：
- 最大连接数限制
- 获取连接超时
- 自动创建和回收连接
- 环境变量配置
"""

import asyncio
import logging
import os

import aiosqlite


class ConnectionPoolExhaustedError(Exception):
    """连接池耗尽异常"""


class ConnectionTimeoutError(Exception):
    """获取连接超时异常"""


class SQLiteConnectionPool:
    """
    SQLite 异步连接池

    使用 asyncio.Queue 管理连接，支持：
    - 最大连接数控制（默认5）
    - 获取超时（默认10秒）
    - 自动重试机制（最多3次）
    - 环境变量配置覆盖
    """

    def __init__(
        self,
        db_path: str,
        max_connections: int = 5,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        self.db_path = db_path
        self.max_connections = max(max_connections, int(os.getenv("SQLITE_MAX_CONNECTIONS", "5")))
        self.timeout = max(timeout, float(os.getenv("SQLITE_TIMEOUT", "10.0")))
        self.max_retries = max(max_retries, int(os.getenv("SQLITE_MAX_RETRIES", "3")))

        self._pool: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue(
            maxsize=self.max_connections
        )
        self._initialized = False
        self._lock = asyncio.Lock()
        self._current_connections: int = 0
        self._logger = logging.getLogger(__name__)

    async def _create_connection(self) -> aiosqlite.Connection:
        """创建新的数据库连接"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    async def initialize(self) -> None:
        """初始化连接池（创建初始连接）"""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            for _ in range(self.max_connections):
                try:
                    conn = await self._create_connection()
                    await self._pool.put(conn)
                    self._current_connections += 1
                except Exception as e:
                    self._logger.error(f"Failed to create initial connection: {e}")
                    raise

            self._initialized = True
            self._logger.info(
                f"SQLite connection pool initialized with {self.max_connections} connections"
            )

    async def get_connection(self) -> aiosqlite.Connection:
        """
        从池中获取可用连接

        如果池中没有可用连接且未达到最大连接数，则创建新连接。
        否则等待其他协程释放连接。

        Raises:
            ConnectionPoolExhaustedError: 连接池耗尽
            ConnectionTimeoutError: 获取连接超时
        """
        if not self._initialized:
            await self.initialize()

        for attempt in range(self.max_retries):
            try:
                if not self._pool.empty():
                    conn = await asyncio.wait_for(self._pool.get(), timeout=self.timeout)
                    try:
                        cursor = await conn.execute("SELECT 1")
                        await cursor.close()
                        return conn
                    except Exception as e:
                        self._logger.warning(f"Connection validation failed: {e}")
                        try:
                            await conn.close()
                        except Exception:
                            pass
                        self._current_connections -= 1
                        continue

                if self._current_connections < self.max_connections:
                    async with self._lock:
                        if self._current_connections < self.max_connections:
                            conn = await self._create_connection()
                            self._current_connections += 1
                            return conn

                conn = await asyncio.wait_for(self._pool.get(), timeout=self.timeout)
                return conn

            except asyncio.TimeoutError:
                self._logger.warning(
                    f"Connection pool timeout (attempt {attempt + 1}/{self.max_retries})"
                )
                if attempt == self.max_retries - 1:
                    raise ConnectionTimeoutError(
                        f"Failed to acquire connection after {self.max_retries} attempts "
                        f"(timeout={self.timeout}s)"
                    ) from None

            except Exception as e:
                self._logger.error(f"Error getting connection (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    raise ConnectionPoolExhaustedError(
                        f"Connection pool exhausted after {self.max_retries} retries: {e}"
                    ) from e
                await asyncio.sleep(0.1 * (attempt + 1))

        raise ConnectionPoolExhaustedError("Unexpected error in get_connection")

    async def release_connection(self, conn: aiosqlite.Connection) -> None:
        """
        归还连接到池中

        Args:
            conn: 要归还的数据库连接
        """
        if conn is None:
            return

        try:
            if not self._pool.full():
                await self._pool.put(conn)
            else:
                await conn.close()
                self._current_connections -= 1
                self._logger.debug("Closed excess connection")
        except Exception as e:
            self._logger.error(f"Error releasing connection: {e}")
            try:
                await conn.close()
                self._current_connections -= 1
            except Exception as close_err:
                self._logger.error(f"Error closing connection: {close_err}")

    async def close(self) -> None:
        """关闭所有连接并清空连接池"""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                await conn.close()
                self._current_connections -= 1
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                self._logger.error(f"Error closing connection: {e}")

        self._current_connections = 0
        self._initialized = False
        self._logger.info("SQLite connection pool closed")

    @property
    def available_connections(self) -> int:
        """获取当前可用连接数"""
        return self._pool.qsize()

    @property
    def active_connections(self) -> int:
        """获取当前活跃连接数（已分配但未归还）"""
        return self._current_connections - self._pool.qsize()


__all__ = [
    "SQLiteConnectionPool",
    "ConnectionPoolExhaustedError",
    "ConnectionTimeoutError",
]

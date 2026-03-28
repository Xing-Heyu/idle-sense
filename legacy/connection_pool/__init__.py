"""Connection Pool Manager - Manages connection pools for various backends."""

from __future__ import annotations

import queue
import socket
import threading
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class PoolState(str, Enum):
    ACTIVE = "active"
    DRAINING = "draining"
    CLOSED = "closed"


@dataclass
class PoolStats:
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    pending_requests: int = 0
    total_created: int = 0
    total_destroyed: int = 0
    total_borrowed: int = 0
    total_returned: int = 0
    total_errors: int = 0
    avg_wait_time_ms: float = 0.0
    avg_usage_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_connections": self.total_connections,
            "active_connections": self.active_connections,
            "idle_connections": self.idle_connections,
            "pending_requests": self.pending_requests,
            "total_created": self.total_created,
            "total_destroyed": self.total_destroyed,
            "total_borrowed": self.total_borrowed,
            "total_returned": self.total_returned,
            "total_errors": self.total_errors,
            "avg_wait_time_ms": round(self.avg_wait_time_ms, 3),
            "avg_usage_time_ms": round(self.avg_usage_time_ms, 3)
        }


@dataclass
class PooledConnection(Generic[T]):
    connection: T
    created_at: float
    last_used: float
    borrow_count: int = 0
    is_valid: bool = True

    def touch(self):
        self.last_used = time.time()
        self.borrow_count += 1

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_used


class ConnectionFactory(ABC, Generic[T]):
    @abstractmethod
    def create(self) -> T:
        pass

    @abstractmethod
    def validate(self, connection: T) -> bool:
        pass

    @abstractmethod
    def destroy(self, connection: T):
        pass


class SocketConnectionFactory(ConnectionFactory[socket.socket]):
    def __init__(self, host: str, port: int, timeout: float = 30.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def create(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect((self.host, self.port))
        return sock

    def validate(self, connection: socket.socket) -> bool:
        try:
            connection.setblocking(False)
            try:
                data = connection.recv(1, socket.MSG_PEEK)
                connection.setblocking(True)
                return len(data) > 0 or True
            except BlockingIOError:
                connection.setblocking(True)
                return True
            except Exception:
                return False
        except Exception:
            return False

    def destroy(self, connection: socket.socket):
        with suppress(Exception):
            connection.close()


class ConnectionPool(Generic[T]):
    def __init__(
        self,
        factory: ConnectionFactory[T],
        min_size: int = 1,
        max_size: int = 10,
        max_idle_time: float = 300.0,
        max_lifetime: float = 3600.0,
        validation_interval: float = 60.0,
        acquire_timeout: float = 30.0
    ):
        self.factory = factory
        self.min_size = min_size
        self.max_size = max_size
        self.max_idle_time = max_idle_time
        self.max_lifetime = max_lifetime
        self.validation_interval = validation_interval
        self.acquire_timeout = acquire_timeout

        self._pool: queue.Queue = queue.Queue(maxsize=max_size)
        self._all_connections: dict[int, PooledConnection[T]] = {}
        self._state = PoolState.ACTIVE
        self._lock = threading.RLock()
        self._stats = PoolStats()
        self._wait_times: list[float] = []
        self._usage_times: list[float] = []

        self._initialize()

    def _initialize(self):
        for _ in range(self.min_size):
            try:
                conn = self._create_connection()
                self._pool.put(conn)
            except Exception:
                pass

        self._stats.total_connections = len(self._all_connections)
        self._stats.idle_connections = self._pool.qsize()

    def _create_connection(self) -> PooledConnection[T]:
        connection = self.factory.create()
        pooled = PooledConnection(
            connection=connection,
            created_at=time.time(),
            last_used=time.time()
        )

        with self._lock:
            self._all_connections[id(connection)] = pooled
            self._stats.total_created += 1

        return pooled

    def _destroy_connection(self, pooled: PooledConnection[T]):
        with suppress(Exception):
            self.factory.destroy(pooled.connection)

        with self._lock:
            conn_id = id(pooled.connection)
            self._all_connections.pop(conn_id, None)
            self._stats.total_destroyed += 1

    def _validate_connection(self, pooled: PooledConnection[T]) -> bool:
        if pooled.age_seconds > self.max_lifetime:
            return False

        if pooled.idle_seconds > self.max_idle_time:
            return False

        try:
            return self.factory.validate(pooled.connection)
        except Exception:
            return False

    def acquire(self, timeout: float | None = None) -> PooledConnection[T]:
        if self._state != PoolState.ACTIVE:
            raise RuntimeError("Pool is not active")

        timeout = timeout or self.acquire_timeout
        start_time = time.time()

        while True:
            try:
                pooled = self._pool.get(block=False)

                if self._validate_connection(pooled):
                    pooled.touch()

                    with self._lock:
                        self._stats.active_connections += 1
                        self._stats.idle_connections -= 1
                        self._stats.total_borrowed += 1
                        wait_time = time.time() - start_time
                        self._wait_times.append(wait_time)
                        if len(self._wait_times) > 100:
                            self._wait_times = self._wait_times[-100:]
                        self._stats.avg_wait_time_ms = sum(self._wait_times) / len(self._wait_times) * 1000

                    return pooled
                else:
                    self._destroy_connection(pooled)

            except queue.Empty:
                with self._lock:
                    if len(self._all_connections) < self.max_size:
                        try:
                            pooled = self._create_connection()
                            pooled.touch()
                            self._stats.active_connections += 1
                            self._stats.total_borrowed += 1
                            return pooled
                        except Exception:
                            self._stats.total_errors += 1
                            raise

                remaining = timeout - (time.time() - start_time)
                if remaining <= 0:
                    self._stats.total_errors += 1
                    raise TimeoutError("Failed to acquire connection") from None

                try:
                    pooled = self._pool.get(block=True, timeout=min(remaining, 0.1))

                    if self._validate_connection(pooled):
                        pooled.touch()
                        with self._lock:
                            self._stats.active_connections += 1
                            self._stats.idle_connections -= 1
                            self._stats.total_borrowed += 1
                        return pooled
                    else:
                        self._destroy_connection(pooled)

                except queue.Empty:
                    continue

    def release(self, pooled: PooledConnection[T]):
        if self._state == PoolState.CLOSED:
            self._destroy_connection(pooled)
            return

        with self._lock:
            self._stats.active_connections -= 1
            self._stats.total_returned += 1

        if self._validate_connection(pooled):
            try:
                self._pool.put(pooled, block=False)
                with self._lock:
                    self._stats.idle_connections += 1
            except queue.Full:
                self._destroy_connection(pooled)
        else:
            self._destroy_connection(pooled)

    @contextmanager
    def connection(self, timeout: float | None = None):
        pooled = self.acquire(timeout)
        start_time = time.time()
        try:
            yield pooled.connection
        finally:
            usage_time = time.time() - start_time
            with self._lock:
                self._usage_times.append(usage_time)
                if len(self._usage_times) > 100:
                    self._usage_times = self._usage_times[-100:]
                self._stats.avg_usage_time_ms = sum(self._usage_times) / len(self._usage_times) * 1000
            self.release(pooled)

    def get_stats(self) -> PoolStats:
        with self._lock:
            self._stats.total_connections = len(self._all_connections)
            self._stats.idle_connections = self._pool.qsize()
            self._stats.pending_requests = 0
            return PoolStats(
                **dict(self._stats.__dict__.items())
            )

    def resize(self, min_size: int, max_size: int):
        with self._lock:
            self.min_size = min_size
            self.max_size = max_size

        while len(self._all_connections) > max_size:
            try:
                pooled = self._pool.get(block=False)
                self._destroy_connection(pooled)
            except queue.Empty:
                break

        while len(self._all_connections) < min_size:
            try:
                pooled = self._create_connection()
                self._pool.put(pooled)
            except Exception:
                break

    def drain(self):
        self._state = PoolState.DRAINING

        while True:
            try:
                pooled = self._pool.get(block=False)
                self._destroy_connection(pooled)
            except queue.Empty:
                break

        self._state = PoolState.ACTIVE

    def close(self):
        self._state = PoolState.CLOSED

        while True:
            try:
                pooled = self._pool.get(block=False)
                self._destroy_connection(pooled)
            except queue.Empty:
                break

        with self._lock:
            for pooled in list(self._all_connections.values()):
                self._destroy_connection(pooled)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class PoolManager:
    _instance: PoolManager | None = None
    _lock = threading.RLock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._pools: dict[str, ConnectionPool] = {}
        self._pool_lock = threading.RLock()

    def register_pool(self, name: str, pool: ConnectionPool):
        with self._pool_lock:
            self._pools[name] = pool

    def get_pool(self, name: str) -> ConnectionPool | None:
        return self._pools.get(name)

    def create_socket_pool(
        self,
        name: str,
        host: str,
        port: int,
        min_size: int = 1,
        max_size: int = 10,
        **kwargs
    ) -> ConnectionPool[socket.socket]:
        factory = SocketConnectionFactory(host, port)
        pool = ConnectionPool(
            factory=factory,
            min_size=min_size,
            max_size=max_size,
            **kwargs
        )
        self.register_pool(name, pool)
        return pool

    def get_all_stats(self) -> dict[str, PoolStats]:
        return {name: pool.get_stats() for name, pool in self._pools.items()}

    def close_all(self):
        with self._pool_lock:
            for pool in self._pools.values():
                pool.close()
            self._pools.clear()


__all__ = [
    "PoolState",
    "PoolStats",
    "PooledConnection",
    "ConnectionFactory",
    "SocketConnectionFactory",
    "ConnectionPool",
    "PoolManager",
]

"""Distributed Lock - Distributed locking mechanisms for coordination."""

from __future__ import annotations

import json
import threading
import time
import uuid
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LockState(str, Enum):
    ACQUIRED = "acquired"
    RELEASED = "released"
    EXPIRED = "expired"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class LockInfo:
    lock_id: str
    resource: str
    owner: str
    acquired_at: float
    expires_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def ttl_seconds(self) -> float | None:
        if self.expires_at is None:
            return None
        return max(0, self.expires_at - time.time())

    def to_dict(self) -> dict[str, Any]:
        return {
            "lock_id": self.lock_id,
            "resource": self.resource,
            "owner": self.owner,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "is_expired": self.is_expired,
            "ttl_seconds": self.ttl_seconds
        }


class LockBackend(ABC):
    @abstractmethod
    def acquire(
        self,
        resource: str,
        owner: str,
        ttl_seconds: float | None = None,
        timeout_seconds: float = 0,
        retry_interval: float = 0.1
    ) -> LockInfo | None:
        pass

    @abstractmethod
    def release(self, lock_id: str, owner: str) -> bool:
        pass

    @abstractmethod
    def extend(self, lock_id: str, owner: str, ttl_seconds: float) -> bool:
        pass

    @abstractmethod
    def get_lock(self, resource: str) -> LockInfo | None:
        pass

    @abstractmethod
    def is_locked(self, resource: str) -> bool:
        pass

    @abstractmethod
    def get_all_locks(self) -> list[LockInfo]:
        pass


class MemoryLockBackend(LockBackend):
    def __init__(self):
        self._locks: dict[str, LockInfo] = {}
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)

    def acquire(
        self,
        resource: str,
        owner: str,
        ttl_seconds: float | None = None,
        timeout_seconds: float = 0,
        retry_interval: float = 0.1
    ) -> LockInfo | None:
        start_time = time.time()

        with self._condition:
            while True:
                existing = self._locks.get(resource)

                if existing is None or existing.is_expired:
                    lock_id = str(uuid.uuid4())
                    now = time.time()

                    lock_info = LockInfo(
                        lock_id=lock_id,
                        resource=resource,
                        owner=owner,
                        acquired_at=now,
                        expires_at=now + ttl_seconds if ttl_seconds else None
                    )

                    self._locks[resource] = lock_info
                    return lock_info

                if timeout_seconds <= 0:
                    return None

                elapsed = time.time() - start_time
                if elapsed >= timeout_seconds:
                    return None

                wait_time = min(retry_interval, timeout_seconds - elapsed)
                self._condition.wait(wait_time)

    def release(self, lock_id: str, owner: str) -> bool:
        with self._lock:
            for resource, lock in list(self._locks.items()):
                if lock.lock_id == lock_id and lock.owner == owner:
                    del self._locks[resource]
                    return True
            return False

    def extend(self, lock_id: str, owner: str, ttl_seconds: float) -> bool:
        with self._lock:
            for lock in self._locks.values():
                if lock.lock_id == lock_id and lock.owner == owner:
                    if lock.is_expired:
                        return False
                    lock.expires_at = time.time() + ttl_seconds
                    return True
            return False

    def get_lock(self, resource: str) -> LockInfo | None:
        with self._lock:
            lock = self._locks.get(resource)
            if lock and not lock.is_expired:
                return lock
            return None

    def is_locked(self, resource: str) -> bool:
        return self.get_lock(resource) is not None

    def get_all_locks(self) -> list[LockInfo]:
        with self._lock:
            return [
                lock for lock in self._locks.values()
                if not lock.is_expired
            ]


class RedisLockBackend(LockBackend):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        prefix: str = "lock:"
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.prefix = prefix
        self._client = None

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
                    decode_responses=True
                )
            except ImportError as e:
                raise ImportError("Redis support requires redis package") from e
        return self._client

    def _make_key(self, resource: str) -> str:
        return f"{self.prefix}{resource}"

    def acquire(
        self,
        resource: str,
        owner: str,
        ttl_seconds: float | None = None,
        timeout_seconds: float = 0,
        retry_interval: float = 0.1
    ) -> LockInfo | None:
        key = self._make_key(resource)
        lock_id = str(uuid.uuid4())
        now = time.time()

        lock_data = json.dumps({
            "lock_id": lock_id,
            "owner": owner,
            "acquired_at": now
        })

        start_time = time.time()

        while True:
            acquired = self.client.set(
                key,
                lock_data,
                nx=True,
                ex=int(ttl_seconds) if ttl_seconds else None
            )

            if acquired:
                return LockInfo(
                    lock_id=lock_id,
                    resource=resource,
                    owner=owner,
                    acquired_at=now,
                    expires_at=now + ttl_seconds if ttl_seconds else None
                )

            if timeout_seconds <= 0:
                return None

            elapsed = time.time() - start_time
            if elapsed >= timeout_seconds:
                return None

            time.sleep(min(retry_interval, timeout_seconds - elapsed))

    def release(self, lock_id: str, owner: str) -> bool:
        script = """
        local key = KEYS[1]
        local lock_id = ARGV[1]
        local owner = ARGV[2]
        local data = redis.call('GET', key)

        if data then
            local decoded = cjson.decode(data)
            if decoded.lock_id == lock_id and decoded.owner == owner then
                redis.call('DEL', key)
                return 1
            end
        end
        return 0
        """

        for resource in self.client.keys(f"{self.prefix}*"):
            key = resource if isinstance(resource, str) else resource.decode()
            result = self.client.eval(
                script, 1, key, lock_id, owner
            )
            if result:
                return True

        return False

    def extend(self, lock_id: str, owner: str, ttl_seconds: float) -> bool:
        script = """
        local key = KEYS[1]
        local lock_id = ARGV[1]
        local owner = ARGV[2]
        local ttl = tonumber(ARGV[3])
        local data = redis.call('GET', key)

        if data then
            local decoded = cjson.decode(data)
            if decoded.lock_id == lock_id and decoded.owner == owner then
                redis.call('EXPIRE', key, ttl)
                return 1
            end
        end
        return 0
        """

        for resource in self.client.keys(f"{self.prefix}*"):
            key = resource if isinstance(resource, str) else resource.decode()
            result = self.client.eval(
                script, 1, key, lock_id, owner, int(ttl_seconds)
            )
            if result:
                return True

        return False

    def get_lock(self, resource: str) -> LockInfo | None:
        key = self._make_key(resource)
        data = self.client.get(key)

        if not data:
            return None

        try:
            decoded = json.loads(data)
            ttl = self.client.ttl(key)

            return LockInfo(
                lock_id=decoded["lock_id"],
                resource=resource,
                owner=decoded["owner"],
                acquired_at=decoded["acquired_at"],
                expires_at=time.time() + ttl if ttl > 0 else None
            )
        except (json.JSONDecodeError, KeyError):
            return None

    def is_locked(self, resource: str) -> bool:
        return self.client.exists(self._make_key(resource)) > 0

    def get_all_locks(self) -> list[LockInfo]:
        locks = []

        for key in self.client.keys(f"{self.prefix}*"):
            if isinstance(key, bytes):
                key = key.decode()

            resource = key[len(self.prefix):]
            lock = self.get_lock(resource)
            if lock:
                locks.append(lock)

        return locks


class DistributedLock:
    def __init__(
        self,
        backend: LockBackend | None = None,
        default_ttl: float | None = 30.0,
        owner: str | None = None
    ):
        self.backend = backend or MemoryLockBackend()
        self.default_ttl = default_ttl
        self.owner = owner or f"node_{uuid.uuid4().hex[:8]}"
        self._held_locks: dict[str, LockInfo] = {}
        self._lock = threading.RLock()

    def acquire(
        self,
        resource: str,
        ttl_seconds: float | None = None,
        timeout_seconds: float = 0,
        retry_interval: float = 0.1
    ) -> LockState:
        lock_info = self.backend.acquire(
            resource=resource,
            owner=self.owner,
            ttl_seconds=ttl_seconds or self.default_ttl,
            timeout_seconds=timeout_seconds,
            retry_interval=retry_interval
        )

        if lock_info:
            with self._lock:
                self._held_locks[lock_info.lock_id] = lock_info
            return LockState.ACQUIRED

        return LockState.TIMEOUT if timeout_seconds > 0 else LockState.FAILED

    def release(self, lock_id: str) -> LockState:
        with self._lock:
            lock_info = self._held_locks.pop(lock_id, None)

        if not lock_info:
            return LockState.FAILED

        if self.backend.release(lock_id, self.owner):
            return LockState.RELEASED

        return LockState.EXPIRED

    def extend(self, lock_id: str, ttl_seconds: float) -> bool:
        return self.backend.extend(lock_id, self.owner, ttl_seconds)

    @contextmanager
    def lock(
        self,
        resource: str,
        ttl_seconds: float | None = None,
        timeout_seconds: float = 10.0,
        retry_interval: float = 0.1
    ):
        state = self.acquire(
            resource=resource,
            ttl_seconds=ttl_seconds,
            timeout_seconds=timeout_seconds,
            retry_interval=retry_interval
        )

        if state != LockState.ACQUIRED:
            raise TimeoutError(f"Failed to acquire lock for {resource}")

        lock_id = None
        with self._lock:
            for lid, info in self._held_locks.items():
                if info.resource == resource:
                    lock_id = lid
                    break

        try:
            yield state
        finally:
            if lock_id:
                self.release(lock_id)

    def is_locked(self, resource: str) -> bool:
        return self.backend.is_locked(resource)

    def get_lock_info(self, resource: str) -> LockInfo | None:
        return self.backend.get_lock(resource)

    def release_all(self) -> int:
        count = 0
        with self._lock:
            lock_ids = list(self._held_locks.keys())

        for lock_id in lock_ids:
            if self.release(lock_id) == LockState.RELEASED:
                count += 1

        return count


class ReadWriteLock:
    def __init__(self, backend: LockBackend | None = None):
        self.backend = backend or MemoryLockBackend()
        self._read_lock = DistributedLock(backend=backend, owner="read_lock")
        self._write_lock = DistributedLock(backend=backend, owner="write_lock")
        self._counter_resource = "__rw_counter__"

    def acquire_read(self, resource: str, timeout: float = 10.0) -> bool:
        counter_key = f"{resource}:readers"

        with self._read_lock.lock(counter_key, timeout_seconds=timeout):
            current = self._get_reader_count(resource)
            self._set_reader_count(resource, current + 1)

            if current == 0 and self._write_lock.acquire(resource, timeout_seconds=timeout) != LockState.ACQUIRED:
                self._set_reader_count(resource, current)
                return False

        return True

    def release_read(self, resource: str):
        counter_key = f"{resource}:readers"

        with self._read_lock.lock(counter_key):
            current = self._get_reader_count(resource)
            self._set_reader_count(resource, max(0, current - 1))

            if current == 1:
                self._write_lock.release(
                    self._get_write_lock_id(resource)
                )

    def acquire_write(self, resource: str, timeout: float = 10.0) -> bool:
        return self._write_lock.acquire(resource, timeout_seconds=timeout) == LockState.ACQUIRED

    def release_write(self, resource: str):
        lock_id = self._get_write_lock_id(resource)
        if lock_id:
            self._write_lock.release(lock_id)

    def _get_reader_count(self, resource: str) -> int:
        lock = self.backend.get_lock(f"{resource}:reader_count")
        if lock and lock.metadata:
            return lock.metadata.get("count", 0)
        return 0

    def _set_reader_count(self, resource: str, count: int):
        pass

    def _get_write_lock_id(self, resource: str) -> str | None:
        lock = self.backend.get_lock(resource)
        return lock.lock_id if lock else None

    @contextmanager
    def read(self, resource: str, timeout: float = 10.0):
        if not self.acquire_read(resource, timeout):
            raise TimeoutError(f"Failed to acquire read lock for {resource}")
        try:
            yield
        finally:
            self.release_read(resource)

    @contextmanager
    def write(self, resource: str, timeout: float = 10.0):
        if not self.acquire_write(resource, timeout):
            raise TimeoutError(f"Failed to acquire write lock for {resource}")
        try:
            yield
        finally:
            self.release_write(resource)


class Semaphore:
    def __init__(
        self,
        name: str,
        max_count: int,
        backend: LockBackend | None = None
    ):
        self.name = name
        self.max_count = max_count
        self.backend = backend or MemoryLockBackend()
        self._lock = DistributedLock(backend=backend)

    def acquire(self, timeout: float = 10.0) -> bool:
        for i in range(self.max_count):
            slot = f"{self.name}:slot:{i}"
            if self._lock.acquire(slot, timeout_seconds=0) == LockState.ACQUIRED:
                return True

        start = time.time()
        while time.time() - start < timeout:
            for i in range(self.max_count):
                slot = f"{self.name}:slot:{i}"
                if self._lock.acquire(slot, timeout_seconds=0) == LockState.ACQUIRED:
                    return True
            time.sleep(0.1)

        return False

    def release(self):
        for i in range(self.max_count):
            slot = f"{self.name}:slot:{i}"
            if self._lock.is_locked(slot):
                lock_info = self._lock.get_lock_info(slot)
                if lock_info:
                    self._lock.release(lock_info.lock_id)
                    return True
        return False

    @contextmanager
    def acquire_context(self, timeout: float = 10.0):
        if not self.acquire(timeout):
            raise TimeoutError(f"Failed to acquire semaphore {self.name}")
        try:
            yield
        finally:
            self.release()


__all__ = [
    "LockState",
    "LockInfo",
    "LockBackend",
    "MemoryLockBackend",
    "RedisLockBackend",
    "DistributedLock",
    "ReadWriteLock",
    "Semaphore",
]

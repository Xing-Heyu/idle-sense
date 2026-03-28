"""
Distributed Storage Module - Enhanced storage with replication and caching.

Implements:
- etcd backend for distributed configuration
- Cache layer for performance optimization
- Replication support for high availability
- Sharding support for scalability
- Distributed locks for coordination

References:
- etcd: https://etcd.io/docs/v3.5/learning/api/
- Redis Cluster: https://redis.io/docs/management/scaling/
- Cassandra: https://cassandra.apache.org/doc/latest/cassandra/architecture/overview.html
"""

import asyncio
import contextlib
import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional


class ConsistencyLevel(Enum):
    ONE = "one"
    QUORUM = "quorum"
    ALL = "all"


class ReplicationMode(Enum):
    NONE = "none"
    ASYNC = "async"
    SYNC = "sync"


@dataclass
class StorageConfig:
    backend: str = "memory"
    ttl: int = 86400
    replication_factor: int = 1
    consistency_level: ConsistencyLevel = ConsistencyLevel.QUORUM
    cache_enabled: bool = True
    cache_ttl: int = 300
    cache_max_size: int = 10000
    connection_timeout: float = 5.0
    operation_timeout: float = 30.0
    retry_count: int = 3
    retry_delay: float = 0.1

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "ttl": self.ttl,
            "replication_factor": self.replication_factor,
            "consistency_level": self.consistency_level.value,
            "cache_enabled": self.cache_enabled,
            "cache_ttl": self.cache_ttl,
            "cache_max_size": self.cache_max_size,
        }


class CacheLayer:
    """LRU cache layer for storage optimization."""

    def __init__(self, max_size: int = 10000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: dict[str, tuple[Any, float]] = {}
        self._access_order: list[str] = []
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            self._misses += 1
            return None

        value, expiry = self._cache[key]
        if time.time() > expiry:
            del self._cache[key]
            self._access_order.remove(key)
            self._misses += 1
            return None

        self._access_order.remove(key)
        self._access_order.append(key)
        self._hits += 1
        return value

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        ttl = ttl or self.default_ttl

        if key in self._cache:
            self._access_order.remove(key)
        elif len(self._cache) >= self.max_size:
            oldest = self._access_order.pop(0)
            del self._cache[oldest]

        self._cache[key] = (value, time.time() + ttl)
        self._access_order.append(key)

    def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            self._access_order.remove(key)
            return True
        return False

    def clear(self) -> None:
        self._cache.clear()
        self._access_order.clear()

    def get_stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
        }


class DistributedLock:
    """Distributed lock implementation."""

    def __init__(
        self,
        key: str,
        backend: "DistributedStorage",
        ttl: float = 30.0,
        retry_interval: float = 0.1
    ):
        self.key = key
        self.backend = backend
        self.ttl = ttl
        self.retry_interval = retry_interval
        self._lock_id = hashlib.md5(f"{key}:{time.time()}".encode()).hexdigest()[:16]
        self._acquired = False

    async def acquire(self, timeout: float = 10.0) -> bool:
        start_time = time.time()

        while time.time() - start_time < timeout:
            lock_key = f"lock:{self.key}"

            result = await self.backend._raw_put(
                lock_key,
                self._lock_id,
                nx=True,
                ttl=self.ttl
            )

            if result:
                self._acquired = True
                return True

            await asyncio.sleep(self.retry_interval)

        return False

    async def release(self) -> bool:
        if not self._acquired:
            return False

        lock_key = f"lock:{self.key}"

        current = await self.backend._raw_get(lock_key)
        if current == self._lock_id:
            await self.backend._raw_delete(lock_key)
            self._acquired = False
            return True

        return False

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()


class DistributedStorage(ABC):
    """Abstract base class for distributed storage backends."""

    def __init__(self, config: StorageConfig = None):
        self.config = config or StorageConfig()
        self._cache = CacheLayer(
            max_size=self.config.cache_max_size,
            default_ttl=self.config.cache_ttl
        ) if self.config.cache_enabled else None

    @abstractmethod
    async def _raw_get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    async def _raw_put(
        self,
        key: str,
        value: Any,
        ttl: int = None,
        nx: bool = False
    ) -> bool:
        pass

    @abstractmethod
    async def _raw_delete(self, key: str) -> bool:
        pass

    @abstractmethod
    async def _raw_keys(self, pattern: str = None) -> list[str]:
        pass

    async def get(self, key: str) -> Optional[Any]:
        if self._cache:
            cached = self._cache.get(key)
            if cached is not None:
                return cached

        value = await self._raw_get(key)

        if value is not None and self._cache:
            self._cache.set(key, value)

        return value

    async def put(
        self,
        key: str,
        value: Any,
        ttl: int = None,
        nx: bool = False
    ) -> bool:
        result = await self._raw_put(key, value, ttl, nx)

        if result and self._cache:
            self._cache.set(key, value, ttl or self.config.ttl)

        return result

    async def delete(self, key: str) -> bool:
        if self._cache:
            self._cache.delete(key)

        return await self._raw_delete(key)

    async def keys(self, pattern: str = None) -> list[str]:
        return await self._raw_keys(pattern)

    async def exists(self, key: str) -> bool:
        value = await self.get(key)
        return value is not None

    def create_lock(
        self,
        key: str,
        ttl: float = 30.0
    ) -> DistributedLock:
        return DistributedLock(key, self, ttl)

    def get_cache_stats(self) -> dict[str, Any]:
        if self._cache:
            return self._cache.get_stats()
        return {"enabled": False}


class MemoryDistributedStorage(DistributedStorage):
    """In-memory distributed storage for development and testing."""

    def __init__(self, config: StorageConfig = None):
        super().__init__(config)
        self._data: dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    async def _raw_get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._data:
                return None

            value, expiry = self._data[key]
            if time.time() > expiry:
                del self._data[key]
                return None

            return value

    async def _raw_put(
        self,
        key: str,
        value: Any,
        ttl: int = None,
        nx: bool = False
    ) -> bool:
        async with self._lock:
            if nx and key in self._data:
                return False

            self._data[key] = (value, time.time() + (ttl or self.config.ttl))
            return True

    async def _raw_delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    async def _raw_keys(self, pattern: str = None) -> list[str]:
        async with self._lock:
            keys = list(self._data.keys())

            if pattern:
                import fnmatch
                keys = [k for k in keys if fnmatch.fnmatch(k, pattern)]

            return keys

    async def get_stats(self) -> dict[str, Any]:
        async with self._lock:
            return {
                "backend": "memory",
                "total_keys": len(self._data),
                "cache": self.get_cache_stats(),
            }


class RedisDistributedStorage(DistributedStorage):
    """Redis-based distributed storage with cluster support."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        config: StorageConfig = None
    ):
        super().__init__(config)
        self.redis_url = redis_url
        self._client = None
        self._cluster_nodes: list[str] = []

    async def _get_client(self):
        if self._client is None:
            try:
                import redis.asyncio as redis
                self._client = redis.from_url(
                    self.redis_url,
                    decode_responses=True
                )
            except ImportError as e:
                raise ImportError(
                    "Redis storage requires the redis package. "
                    "Install with: pip install redis"
                ) from e
        return self._client

    async def _raw_get(self, key: str) -> Optional[Any]:
        client = await self._get_client()
        data = await client.get(key)

        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        return None

    async def _raw_put(
        self,
        key: str,
        value: Any,
        ttl: int = None,
        nx: bool = False
    ) -> bool:
        client = await self._get_client()

        serialized = json.dumps(value) if not isinstance(value, str) else value

        if nx:
            result = await client.set(
                key,
                serialized,
                ex=ttl or self.config.ttl,
                nx=True
            )
            return result is not None
        else:
            await client.set(key, serialized, ex=ttl or self.config.ttl)
            return True

    async def _raw_delete(self, key: str) -> bool:
        client = await self._get_client()
        result = await client.delete(key)
        return result > 0

    async def _raw_keys(self, pattern: str = None) -> list[str]:
        client = await self._get_client()
        pattern = pattern or "*"

        keys = []
        async for key in client.scan_iter(match=pattern):
            keys.append(key)

        return keys

    async def get_stats(self) -> dict[str, Any]:
        client = await self._get_client()
        info = await client.info()

        return {
            "backend": "redis",
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "total_keys": await client.dbsize(),
            "cache": self.get_cache_stats(),
        }


class EtcdDistributedStorage(DistributedStorage):
    """etcd-based distributed storage for configuration and coordination.

    etcd is a strongly consistent, distributed key-value store.
    Ideal for configuration management and distributed coordination.

    Reference: https://etcd.io/docs/v3.5/learning/api/
    """

    def __init__(
        self,
        etcd_endpoints: list[str] = None,
        config: StorageConfig = None
    ):
        super().__init__(config)
        self.etcd_endpoints = etcd_endpoints or ["http://localhost:2379"]
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                import etcd3
                self._client = etcd3.client(
                    host=self.etcd_endpoints[0].split("://")[1].split(":")[0],
                    port=int(self.etcd_endpoints[0].split(":")[-1])
                )
            except ImportError as e:
                raise ImportError(
                    "etcd storage requires the etcd3 package. "
                    "Install with: pip install etcd3"
                ) from e
        return self._client

    async def _raw_get(self, key: str) -> Optional[Any]:
        client = await self._get_client()

        value, metadata = client.get(key)

        if value:
            try:
                return json.loads(value.decode())
            except json.JSONDecodeError:
                return value.decode()
        return None

    async def _raw_put(
        self,
        key: str,
        value: Any,
        ttl: int = None,
        nx: bool = False
    ) -> bool:
        client = await self._get_client()

        serialized = json.dumps(value) if not isinstance(value, str) else value

        if nx:
            result = client.put_if_not_exists(key, serialized)
            return result

        lease = None
        if ttl:
            lease = client.lease(ttl)

        client.put(key, serialized, lease=lease)
        return True

    async def _raw_delete(self, key: str) -> bool:
        client = await self._get_client()
        result = client.delete(key)
        return result.deleted > 0

    async def _raw_keys(self, pattern: str = None) -> list[str]:
        client = await self._get_client()

        prefix = pattern.rstrip("*") if pattern else ""

        keys = []
        for _value, metadata in client.get_prefix(prefix):
            keys.append(metadata.key.decode())

        return keys

    async def watch(
        self,
        key: str,
        callback: Callable[[str, Any], None]
    ) -> None:
        client = await self._get_client()

        events_iterator, cancel = client.watch(key)

        for event in events_iterator:
            if hasattr(event, "value"):
                value = event.value.decode() if event.value else None
                with contextlib.suppress(json.JSONDecodeError):
                    value = json.loads(value) if value else None
                callback(event.key.decode(), value)

    async def get_stats(self) -> dict[str, Any]:
        client = await self._get_client()

        status = client.status

        return {
            "backend": "etcd",
            "endpoints": self.etcd_endpoints,
            "cluster_id": status.cluster_id if status else "unknown",
            "cache": self.get_cache_stats(),
        }


class ShardedStorage:
    """Sharded storage for horizontal scaling.

    Implements consistent hashing for key distribution.
    """

    def __init__(
        self,
        shards: list[DistributedStorage],
        replication_factor: int = 1
    ):
        self.shards = shards
        self.replication_factor = min(replication_factor, len(shards))
        self._ring: dict[int, DistributedStorage] = {}
        self._build_ring()

    def _build_ring(self):
        virtual_nodes = 150

        for i, shard in enumerate(self.shards):
            for j in range(virtual_nodes):
                key = hashlib.md5(f"shard:{i}:node:{j}".encode()).hexdigest()
                self._ring[int(key, 16)] = shard

    def _get_shard(self, key: str) -> DistributedStorage:
        key_hash = int(hashlib.md5(key.encode()).hexdigest(), 16)

        sorted_keys = sorted(self._ring.keys())

        for ring_key in sorted_keys:
            if key_hash <= ring_key:
                return self._ring[ring_key]

        return self._ring[sorted_keys[0]]

    def _get_shards_for_key(self, key: str) -> list[DistributedStorage]:
        key_hash = int(hashlib.md5(key.encode()).hexdigest(), 16)

        sorted_keys = sorted(self._ring.keys())

        shards = []
        for ring_key in sorted_keys:
            if key_hash <= ring_key and len(shards) < self.replication_factor:
                shard = self._ring[ring_key]
                if shard not in shards:
                    shards.append(shard)

        while len(shards) < self.replication_factor:
            for ring_key in sorted_keys:
                shard = self._ring[ring_key]
                if shard not in shards:
                    shards.append(shard)
                    if len(shards) >= self.replication_factor:
                        break

        return shards

    async def get(self, key: str) -> Optional[Any]:
        shards = self._get_shards_for_key(key)

        for shard in shards:
            try:
                value = await shard.get(key)
                if value is not None:
                    return value
            except Exception:
                continue

        return None

    async def put(
        self,
        key: str,
        value: Any,
        ttl: int = None
    ) -> bool:
        shards = self._get_shards_for_key(key)

        tasks = []
        for shard in shards:
            tasks.append(shard.put(key, value, ttl))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return any(r is True for r in results if not isinstance(r, Exception))

    async def delete(self, key: str) -> bool:
        shards = self._get_shards_for_key(key)

        tasks = []
        for shard in shards:
            tasks.append(shard.delete(key))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return any(r is True for r in results if not isinstance(r, Exception))

    async def get_stats(self) -> dict[str, Any]:
        shard_stats = []

        for i, shard in enumerate(self.shards):
            stats = await shard.get_stats()
            stats["shard_id"] = i
            shard_stats.append(stats)

        return {
            "backend": "sharded",
            "shard_count": len(self.shards),
            "replication_factor": self.replication_factor,
            "shards": shard_stats,
        }


def create_distributed_storage(
    backend: str = "memory",
    config: StorageConfig = None,
    **kwargs
) -> DistributedStorage:
    """Factory function to create distributed storage backend.

    Args:
        backend: Storage backend type ('memory', 'redis', 'etcd')
        config: Storage configuration
        **kwargs: Backend-specific configuration

    Returns:
        DistributedStorage instance
    """
    config = config or StorageConfig(backend=backend)

    if backend == "memory":
        return MemoryDistributedStorage(config)
    elif backend == "redis":
        return RedisDistributedStorage(
            redis_url=kwargs.get("redis_url", "redis://localhost:6379/0"),
            config=config
        )
    elif backend == "etcd":
        return EtcdDistributedStorage(
            etcd_endpoints=kwargs.get("etcd_endpoints", ["http://localhost:2379"]),
            config=config
        )
    else:
        raise ValueError(f"Unknown storage backend: {backend}")


__all__ = [
    "ConsistencyLevel",
    "ReplicationMode",
    "StorageConfig",
    "CacheLayer",
    "DistributedLock",
    "DistributedStorage",
    "MemoryDistributedStorage",
    "RedisDistributedStorage",
    "EtcdDistributedStorage",
    "ShardedStorage",
    "create_distributed_storage",
]

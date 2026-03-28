"""Cache Layer - Multi-backend caching with TTL and LRU eviction."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class CacheEntry(Generic[V]):
    key: str
    value: V
    created_at: float
    expires_at: float | None = None
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)
    size_bytes: int = 0

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def touch(self):
        self.access_count += 1
        self.last_accessed = time.time()


class CacheBackend(ABC, Generic[K, V]):
    @abstractmethod
    def get(self, key: K) -> CacheEntry[V] | None:
        pass

    @abstractmethod
    def set(self, key: K, entry: CacheEntry[V]) -> bool:
        pass

    @abstractmethod
    def delete(self, key: K) -> bool:
        pass

    @abstractmethod
    def exists(self, key: K) -> bool:
        pass

    @abstractmethod
    def clear(self) -> int:
        pass

    @abstractmethod
    def keys(self) -> list[K]:
        pass

    @abstractmethod
    def size(self) -> int:
        pass


class MemoryCacheBackend(CacheBackend[str, Any]):
    def __init__(self, max_size: int = 10000, max_memory_mb: int = 100):
        self._cache: dict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._current_memory = 0
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> CacheEntry | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                self._evict(key)
                self._misses += 1
                return None

            self._cache.move_to_end(key)
            entry.touch()
            self._hits += 1
            return entry

    def set(self, key: str, entry: CacheEntry) -> bool:
        with self._lock:
            if key in self._cache:
                old_entry = self._cache[key]
                self._current_memory -= old_entry.size_bytes

            entry.size_bytes = self._estimate_size(entry.value)

            while (
                len(self._cache) >= self.max_size or
                self._current_memory + entry.size_bytes > self.max_memory_bytes
            ):
                if not self._evict_lru():
                    break

            self._cache[key] = entry
            self._current_memory += entry.size_bytes
            return True

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._evict(key)

    def exists(self, key: str) -> bool:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                self._evict(key)
                return False
            return True

    def clear(self) -> int:
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._current_memory = 0
            return count

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._cache.keys())

    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "memory_bytes": self._current_memory,
                "max_memory_bytes": self.max_memory_bytes,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate
            }

    def _evict(self, key: str) -> bool:
        if key in self._cache:
            entry = self._cache.pop(key)
            self._current_memory -= entry.size_bytes
            return True
        return False

    def _evict_lru(self) -> bool:
        if not self._cache:
            return False
        oldest_key = next(iter(self._cache))
        return self._evict(oldest_key)

    def _estimate_size(self, value: Any) -> int:
        try:
            return len(json.dumps(value, ensure_ascii=True))
        except Exception:
            return 1024


class RedisCacheBackend(CacheBackend[str, Any]):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        prefix: str = "idle_sense:"
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
                    decode_responses=False
                )
            except ImportError as e:
                raise ImportError("Redis support requires redis package") from e
        return self._client

    def _make_key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def get(self, key: str) -> CacheEntry | None:
        data = self.client.get(self._make_key(key))
        if data is None:
            return None

        try:
            entry_dict = json.loads(data)
            return CacheEntry(
                key=entry_dict["key"],
                value=json.loads(entry_dict["value"]),
                created_at=entry_dict["created_at"],
                expires_at=entry_dict.get("expires_at"),
                access_count=entry_dict.get("access_count", 0),
                last_accessed=entry_dict.get("last_accessed", time.time()),
                tags=entry_dict.get("tags", [])
            )
        except Exception:
            return None

    def set(self, key: str, entry: CacheEntry) -> bool:
        entry_dict = {
            "key": entry.key,
            "value": json.dumps(entry.value),
            "created_at": entry.created_at,
            "expires_at": entry.expires_at,
            "access_count": entry.access_count,
            "last_accessed": entry.last_accessed,
            "tags": entry.tags
        }

        ttl = None
        if entry.expires_at:
            ttl = int(entry.expires_at - time.time())
            if ttl <= 0:
                return False

        self.client.set(
            self._make_key(key),
            json.dumps(entry_dict),
            ex=ttl
        )
        return True

    def delete(self, key: str) -> bool:
        return bool(self.client.delete(self._make_key(key)))

    def exists(self, key: str) -> bool:
        return bool(self.client.exists(self._make_key(key)))

    def clear(self) -> int:
        keys = self.client.keys(f"{self.prefix}*")
        if keys:
            return self.client.delete(*keys)
        return 0

    def keys(self) -> list[str]:
        keys = self.client.keys(f"{self.prefix}*")
        prefix_len = len(self.prefix)
        return [k.decode()[prefix_len:] for k in keys]

    def size(self) -> int:
        return len(self.keys())


class Cache:
    def __init__(
        self,
        backend: CacheBackend | None = None,
        default_ttl: int | None = 3600
    ):
        self.backend = backend or MemoryCacheBackend()
        self.default_ttl = default_ttl
        self._tag_index: dict[str, set] = {}

    def get(self, key: str, default: Any = None) -> Any:
        entry = self.backend.get(key)
        if entry is None:
            return default
        return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        tags: list[str] | None = None
    ) -> bool:
        ttl = ttl if ttl is not None else self.default_ttl

        created_at = time.time()
        expires_at = created_at + ttl if ttl else None

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=created_at,
            expires_at=expires_at,
            tags=tags or []
        )

        result = self.backend.set(key, entry)

        if result and tags:
            for tag in tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = set()
                self._tag_index[tag].add(key)

        return result

    def delete(self, key: str) -> bool:
        entry = self.backend.get(key)
        if entry and entry.tags:
            for tag in entry.tags:
                if tag in self._tag_index:
                    self._tag_index[tag].discard(key)

        return self.backend.delete(key)

    def exists(self, key: str) -> bool:
        return self.backend.exists(key)

    def clear(self) -> int:
        self._tag_index.clear()
        return self.backend.clear()

    def invalidate_tag(self, tag: str) -> int:
        if tag not in self._tag_index:
            return 0

        keys = list(self._tag_index[tag])
        count = 0

        for key in keys:
            if self.backend.delete(key):
                count += 1

        del self._tag_index[tag]
        return count

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: int | None = None,
        tags: list[str] | None = None
    ) -> Any:
        entry = self.backend.get(key)
        if entry is not None:
            return entry.value

        value = factory()
        self.set(key, value, ttl=ttl, tags=tags)
        return value

    def remember(self, key: str, value: Any, ttl: int | None = None) -> Any:
        return self.get_or_set(key, lambda: value, ttl=ttl)

    def forget(self, key: str) -> bool:
        return self.delete(key)

    def has(self, key: str) -> bool:
        return self.exists(key)

    def increment(self, key: str, amount: int = 1) -> int:
        value = self.get(key, 0)
        if not isinstance(value, (int, float)):
            value = 0
        new_value = int(value) + amount
        self.set(key, new_value)
        return new_value

    def decrement(self, key: str, amount: int = 1) -> int:
        return self.increment(key, -amount)

    def stats(self) -> dict[str, Any]:
        stats = {
            "size": self.backend.size(),
            "tags": len(self._tag_index)
        }

        if isinstance(self.backend, MemoryCacheBackend):
            stats.update(self.backend.stats())

        return stats


def cached(
    key: str | None = None,
    ttl: int | None = None,
    tags: list[str] | None = None,
    cache: Cache | None = None
):
    _cache = cache or Cache()

    def decorator(func: Callable) -> Callable:
        _key = key or f"func:{func.__module__}:{func.__qualname__}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = _key
            if args or kwargs:
                arg_hash = hashlib.md5(
                    json.dumps((args, sorted(kwargs.items())), sort_keys=True, ensure_ascii=True).encode("utf-8")
                ).hexdigest()[:8]
                cache_key = f"{_key}:{arg_hash}"

            return _cache.get_or_set(
                cache_key,
                lambda: func(*args, **kwargs),
                ttl=ttl,
                tags=tags
            )

        wrapper.cache_clear = lambda: _cache.delete(_key)
        wrapper.cache_key = _key

        return wrapper

    return decorator


class CacheManager:
    _instance: CacheManager | None = None
    _caches: dict[str, Cache] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_cache(self, name: str = "default") -> Cache:
        if name not in self._caches:
            self._caches[name] = Cache()
        return self._caches[name]

    def create_cache(
        self,
        name: str,
        backend: CacheBackend,
        default_ttl: int | None = None
    ) -> Cache:
        cache = Cache(backend=backend, default_ttl=default_ttl)
        self._caches[name] = cache
        return cache

    def clear_all(self):
        for cache in self._caches.values():
            cache.clear()

    def stats_all(self) -> dict[str, dict[str, Any]]:
        return {name: cache.stats() for name, cache in self._caches.items()}


__all__ = [
    "CacheEntry",
    "CacheBackend",
    "MemoryCacheBackend",
    "RedisCacheBackend",
    "Cache",
    "cached",
    "CacheManager",
]

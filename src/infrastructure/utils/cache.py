"""
多级缓存系统

提供 L1 内存缓存和 L2 Redis 缓存的多级缓存策略
"""

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Optional


@dataclass
class CacheEntry:
    """缓存条目"""

    value: Any
    expire_at: float

    def is_expired(self) -> bool:
        return time.time() > self.expire_at


class MemoryCache:
    """
    L1 内存缓存

    线程安全的内存缓存实现，支持 TTL 过期
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self._cache: dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值"""
        with self._lock:
            if len(self._cache) >= self._max_size and key not in self._cache:
                self._evict_expired()
                if len(self._cache) >= self._max_size:
                    self._evict_oldest()

            expire_at = time.time() + (ttl or self._default_ttl)
            self._cache[key] = CacheEntry(value=value, expire_at=expire_at)

    def delete(self, key: str) -> bool:
        """删除缓存值"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def _evict_expired(self) -> int:
        """清理过期条目"""
        current_time = time.time()
        expired_keys = [
            k for k, v in self._cache.items() if v.expire_at < current_time
        ]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)

    def _evict_oldest(self) -> None:
        """清理最旧的条目"""
        if self._cache:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].expire_at)
            del self._cache[oldest_key]

    def stats(self) -> dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
            }


class MultiLevelCache:
    """
    多级缓存

    组合 L1 内存缓存和可选的 L2 Redis 缓存
    """

    def __init__(
        self,
        l1_cache: Optional[MemoryCache] = None,
        l2_client: Optional[Any] = None,
        l2_prefix: str = "cache:",
    ):
        self.l1 = l1_cache or MemoryCache()
        self.l2 = l2_client
        self.l2_prefix = l2_prefix

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值（先 L1 后 L2）"""
        value = self.l1.get(key)
        if value is not None:
            return value

        if self.l2:
            try:
                l2_key = f"{self.l2_prefix}{key}"
                value = self.l2.get(l2_key)
                if value is not None:
                    self.l1.set(key, value)
                    return value
            except Exception:
                pass

        return None

    def set(
        self,
        key: str,
        value: Any,
        ttl_l1: int = 300,
        ttl_l2: int = 3600,
    ) -> None:
        """设置缓存值（同时设置 L1 和 L2）"""
        self.l1.set(key, value, ttl_l1)

        if self.l2:
            try:
                l2_key = f"{self.l2_prefix}{key}"
                self.l2.set(l2_key, value, ex=ttl_l2)
            except Exception:
                pass

    def delete(self, key: str) -> bool:
        """删除缓存值"""
        result = self.l1.delete(key)

        if self.l2:
            try:
                l2_key = f"{self.l2_prefix}{key}"
                self.l2.delete(l2_key)
            except Exception:
                pass

        return result

    def cached(
        self,
        key_prefix: str = "",
        ttl_l1: int = 300,
        ttl_l2: int = 3600,
    ) -> Callable:
        """缓存装饰器"""

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                cache_key = self._generate_key(key_prefix, func.__name__, args, kwargs)

                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value

                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl_l1, ttl_l2)
                return result

            return wrapper

        return decorator

    def _generate_key(
        self,
        prefix: str,
        func_name: str,
        args: tuple,
        kwargs: dict,
    ) -> str:
        """生成缓存键"""
        key_data = json.dumps(
            {"args": str(args)[:200], "kwargs": str(kwargs)[:200]},
            sort_keys=True,
        )
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:8]
        return f"{prefix}:{func_name}:{key_hash}"

    def stats(self) -> dict[str, Any]:
        """获取缓存统计"""
        return {
            "l1": self.l1.stats(),
            "l2_enabled": self.l2 is not None,
        }


def create_cache(
    max_size: int = 1000,
    default_ttl: int = 300,
    l2_client: Optional[Any] = None,
) -> MultiLevelCache:
    """创建多级缓存实例"""
    l1 = MemoryCache(max_size=max_size, default_ttl=default_ttl)
    return MultiLevelCache(l1_cache=l1, l2_client=l2_client)


__all__ = [
    "CacheEntry",
    "MemoryCache",
    "MultiLevelCache",
    "create_cache",
]

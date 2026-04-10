"""
缓存工具模块

提供：
- 内存缓存实现
- 缓存装饰器
- LRU缓存策略
- 缓存过期机制

使用示例：
    from src.infrastructure.utils import cache_result, MemoryCache

    # 使用装饰器
    @cache_result(ttl=60)
    def expensive_function():
        return compute_something()

    # 使用缓存类
    cache = MemoryCache(max_size=1000)
    cache.set("key", "value", ttl=60)
    value = cache.get("key")
"""

import functools
import threading
import time
from collections import OrderedDict
from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any, Callable, Generic, Optional, TypeVar

T = TypeVar("T")
K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass
class CacheEntry(Generic[V]):
    """缓存条目"""

    value: V
    expires_at: float
    created_at: float

    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() > self.expires_at


class MemoryCache(Generic[K, V]):
    """
    内存缓存实现

    支持：
    - LRU淘汰策略
    - TTL过期机制
    - 线程安全
    - 最大容量限制

    Examples:
        >>> cache = MemoryCache(max_size=1000)
        >>> cache.set("key", "value", ttl=60)
        >>> cache.get("key")
        'value'
        >>> cache.delete("key")
        >>> cache.get("key") is None
        True
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        初始化缓存

        Args:
            max_size: 最大缓存条目数
            default_ttl: 默认过期时间（秒）
        """
        self._cache: OrderedDict[K, CacheEntry[V]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: K) -> Optional[V]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或已过期则返回None
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            self._hits += 1
            self._cache.move_to_end(key)
            return entry.value

    def set(self, key: K, value: V, ttl: Optional[int] = None) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None表示使用默认值
        """
        with self._lock:
            current_time = time.time()
            ttl = ttl if ttl is not None else self._default_ttl

            entry = CacheEntry(value=value, expires_at=current_time + ttl, created_at=current_time)

            if key in self._cache:
                del self._cache[key]

            self._cache[key] = entry

            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def delete(self, key: K) -> bool:
        """
        删除缓存值

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
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

    def cleanup_expired(self) -> int:
        """
        清理过期条目

        Returns:
            清理的条目数
        """
        with self._lock:
            expired_keys = [key for key, entry in self._cache.items() if entry.is_expired()]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)

    def get_stats(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0

            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "total_requests": total_requests,
            }

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: K) -> bool:
        return self.get(key) is not None


def cache_result(ttl: int = 30, maxsize: int = 128):
    """
    缓存装饰器

    Args:
        ttl: 缓存过期时间（秒）
        maxsize: 最大缓存条目数

    Returns:
        装饰器函数

    Examples:
        >>> @cache_result(ttl=60)
        ... def expensive_function(n):
        ...     print("Computing...")
        ...     return n * 2
        >>> expensive_function(5)  # 第一次调用，会执行
        Computing...
        10
        >>> expensive_function(5)  # 第二次调用，使用缓存
        10
    """
    cache: dict[str, tuple] = {}

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            current_time = time.time()

            if key in cache:
                result, timestamp = cache[key]
                if current_time - timestamp < ttl:
                    return result

            if len(cache) >= maxsize:
                oldest_key = next(iter(cache))
                del cache[oldest_key]

            result = func(*args, **kwargs)
            cache[key] = (result, current_time)
            return result

        wrapper.cache_clear = lambda: cache.clear()
        wrapper.cache_info = lambda: {"size": len(cache), "maxsize": maxsize, "ttl": ttl}

        return wrapper

    return decorator


def cached_method(ttl: int = 30):
    """
    方法缓存装饰器

    专门用于类方法，会自动处理self参数

    Args:
        ttl: 缓存过期时间（秒）

    Returns:
        装饰器函数

    Examples:
        >>> class DataService:
        ...     @cached_method(ttl=60)
        ...     def get_data(self, id):
        ...         return fetch_data(id)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache: dict[int, dict[str, tuple]] = {}

        @functools.wraps(func)
        def wrapper(self, *args, **kwargs) -> T:
            instance_id = id(self)

            if instance_id not in cache:
                cache[instance_id] = {}

            instance_cache = cache[instance_id]
            key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            current_time = time.time()

            if key in instance_cache:
                result, timestamp = instance_cache[key]
                if current_time - timestamp < ttl:
                    return result

            result = func(self, *args, **kwargs)
            instance_cache[key] = (result, current_time)
            return result

        return wrapper

    return decorator


class TTLCache:
    """
    TTL缓存类

    简单的TTL缓存实现，适合存储单一值

    Examples:
        >>> cache = TTLCache(ttl=60)
        >>> cache.set("value")
        >>> cache.get()
        'value'
        >>> time.sleep(61)
        >>> cache.get() is None
        True
    """

    def __init__(self, ttl: int = 300):
        """
        初始化TTL缓存

        Args:
            ttl: 过期时间（秒）
        """
        self._value: Optional[V] = None
        self._expires_at: float = 0
        self._ttl = ttl
        self._lock = threading.Lock()

    def get(self) -> Optional[V]:
        """获取缓存值"""
        with self._lock:
            if self._value is None or time.time() > self._expires_at:
                return None
            return self._value

    def set(self, value: V, ttl: Optional[int] = None) -> None:
        """设置缓存值"""
        with self._lock:
            self._value = value
            self._expires_at = time.time() + (ttl or self._ttl)

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._value = None
            self._expires_at = 0

    def is_valid(self) -> bool:
        """检查缓存是否有效"""
        with self._lock:
            return self._value is not None and time.time() <= self._expires_at


__all__ = [
    "MemoryCache",
    "cache_result",
    "cached_method",
    "TTLCache",
    "CacheEntry",
]

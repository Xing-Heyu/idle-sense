"""Rate Limiter - Rate limiting strategies for task execution."""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class LimitResult(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    THROTTLED = "throttled"


@dataclass
class RateLimitStats:
    total_requests: int = 0
    allowed_requests: int = 0
    denied_requests: int = 0
    throttled_requests: int = 0
    current_rate: float = 0.0
    last_request_time: float = 0.0

    @property
    def denial_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.denied_requests / self.total_requests

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "allowed_requests": self.allowed_requests,
            "denied_requests": self.denied_requests,
            "throttled_requests": self.throttled_requests,
            "denial_rate": round(self.denial_rate, 4),
            "current_rate": round(self.current_rate, 4),
        }


class RateLimiterBackend(ABC):
    @abstractmethod
    def acquire(self, key: str, permits: int = 1) -> LimitResult:
        pass

    @abstractmethod
    def get_stats(self, key: str) -> RateLimitStats:
        pass

    @abstractmethod
    def reset(self, key: str):
        pass


class TokenBucketBackend(RateLimiterBackend):
    def __init__(self, rate: float, burst_size: int, refill_interval: float = 1.0):
        self.rate = rate
        self.burst_size = burst_size
        self.refill_interval = refill_interval

        self._buckets: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def _get_bucket(self, key: str) -> dict[str, Any]:
        if key not in self._buckets:
            self._buckets[key] = {
                "tokens": float(self.burst_size),
                "last_refill": time.time(),
                "stats": RateLimitStats(),
            }
        return self._buckets[key]

    def _refill(self, bucket: dict[str, Any]):
        now = time.time()
        elapsed = now - bucket["last_refill"]

        tokens_to_add = (elapsed / self.refill_interval) * self.rate
        bucket["tokens"] = min(self.burst_size, bucket["tokens"] + tokens_to_add)
        bucket["last_refill"] = now

    def acquire(self, key: str, permits: int = 1) -> LimitResult:
        with self._lock:
            bucket = self._get_bucket(key)
            self._refill(bucket)

            bucket["stats"].total_requests += 1
            bucket["stats"].last_request_time = time.time()

            if bucket["tokens"] >= permits:
                bucket["tokens"] -= permits
                bucket["stats"].allowed_requests += 1
                bucket["stats"].current_rate = self.rate - bucket["tokens"]
                return LimitResult.ALLOWED
            else:
                bucket["stats"].denied_requests += 1
                return LimitResult.DENIED

    def get_stats(self, key: str) -> RateLimitStats:
        with self._lock:
            bucket = self._get_bucket(key)
            self._refill(bucket)
            return bucket["stats"]

    def reset(self, key: str):
        with self._lock:
            if key in self._buckets:
                del self._buckets[key]


class SlidingWindowBackend(RateLimiterBackend):
    def __init__(self, max_requests: int, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        self._windows: dict[str, list[float]] = {}
        self._stats: dict[str, RateLimitStats] = {}
        self._lock = threading.RLock()

    def _cleanup(self, key: str):
        if key not in self._windows:
            return

        cutoff = time.time() - self.window_seconds
        self._windows[key] = [t for t in self._windows[key] if t > cutoff]

    def acquire(self, key: str, permits: int = 1) -> LimitResult:
        with self._lock:
            if key not in self._windows:
                self._windows[key] = []
                self._stats[key] = RateLimitStats()

            self._cleanup(key)

            stats = self._stats[key]
            stats.total_requests += 1
            stats.last_request_time = time.time()

            current_count = len(self._windows[key])

            if current_count + permits <= self.max_requests:
                for _ in range(permits):
                    self._windows[key].append(time.time())

                stats.allowed_requests += 1
                stats.current_rate = len(self._windows[key]) / self.window_seconds
                return LimitResult.ALLOWED
            else:
                stats.denied_requests += 1
                return LimitResult.DENIED

    def get_stats(self, key: str) -> RateLimitStats:
        with self._lock:
            self._cleanup(key)
            return self._stats.get(key, RateLimitStats())

    def reset(self, key: str):
        with self._lock:
            self._windows.pop(key, None)
            self._stats.pop(key, None)


class LeakyBucketBackend(RateLimiterBackend):
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity

        self._buckets: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def _get_bucket(self, key: str) -> dict[str, Any]:
        if key not in self._buckets:
            self._buckets[key] = {"water": 0, "last_leak": time.time(), "stats": RateLimitStats()}
        return self._buckets[key]

    def _leak(self, bucket: dict[str, Any]):
        now = time.time()
        elapsed = now - bucket["last_leak"]

        leaked = elapsed * self.rate
        bucket["water"] = max(0, bucket["water"] - leaked)
        bucket["last_leak"] = now

    def acquire(self, key: str, permits: int = 1) -> LimitResult:
        with self._lock:
            bucket = self._get_bucket(key)
            self._leak(bucket)

            stats = bucket["stats"]
            stats.total_requests += 1
            stats.last_request_time = time.time()

            if bucket["water"] + permits <= self.capacity:
                bucket["water"] += permits
                stats.allowed_requests += 1
                stats.current_rate = bucket["water"] / self.capacity * self.rate
                return LimitResult.ALLOWED
            else:
                stats.denied_requests += 1
                return LimitResult.DENIED

    def get_stats(self, key: str) -> RateLimitStats:
        with self._lock:
            bucket = self._get_bucket(key)
            self._leak(bucket)
            return bucket["stats"]

    def reset(self, key: str):
        with self._lock:
            self._buckets.pop(key, None)


class FixedWindowBackend(RateLimiterBackend):
    def __init__(self, max_requests: int, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        self._windows: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def _get_window_start(self) -> float:
        now = time.time()
        return now - (now % self.window_seconds)

    def acquire(self, key: str, permits: int = 1) -> LimitResult:
        with self._lock:
            window_start = self._get_window_start()

            if key not in self._windows or self._windows[key]["start"] != window_start:
                self._windows[key] = {"start": window_start, "count": 0, "stats": RateLimitStats()}

            window = self._windows[key]
            stats = window["stats"]
            stats.total_requests += 1
            stats.last_request_time = time.time()

            if window["count"] + permits <= self.max_requests:
                window["count"] += permits
                stats.allowed_requests += 1
                stats.current_rate = window["count"] / self.window_seconds
                return LimitResult.ALLOWED
            else:
                stats.denied_requests += 1
                return LimitResult.DENIED

    def get_stats(self, key: str) -> RateLimitStats:
        with self._lock:
            window = self._windows.get(key)
            return window["stats"] if window else RateLimitStats()

    def reset(self, key: str):
        with self._lock:
            self._windows.pop(key, None)


class RateLimiter:
    def __init__(self, backend: RateLimiterBackend | None = None, default_key: str = "default"):
        self.backend = backend or TokenBucketBackend(rate=10.0, burst_size=20)
        self.default_key = default_key

    def acquire(self, key: str | None = None, permits: int = 1) -> LimitResult:
        return self.backend.acquire(key or self.default_key, permits)

    def try_acquire(self, key: str | None = None, permits: int = 1) -> bool:
        return self.acquire(key, permits) == LimitResult.ALLOWED

    def acquire_or_wait(
        self,
        key: str | None = None,
        permits: int = 1,
        timeout: float = 10.0,
        retry_interval: float = 0.1,
    ) -> LimitResult:
        start_time = time.time()

        while True:
            result = self.acquire(key, permits)

            if result == LimitResult.ALLOWED:
                return result

            elapsed = time.time() - start_time
            if elapsed >= timeout:
                return LimitResult.DENIED

            time.sleep(min(retry_interval, timeout - elapsed))

    @contextmanager
    def limit(self, key: str | None = None, permits: int = 1, timeout: float = 10.0):
        result = self.acquire_or_wait(key, permits, timeout)

        if result != LimitResult.ALLOWED:
            raise TimeoutError(f"Rate limit exceeded for key: {key or self.default_key}")

        try:
            yield
        finally:
            pass

    def get_stats(self, key: str | None = None) -> RateLimitStats:
        return self.backend.get_stats(key or self.default_key)

    def reset(self, key: str | None = None):
        self.backend.reset(key or self.default_key)


def rate_limit(rate: float = 10.0, burst_size: int = 20, key_func: Callable | None = None):
    limiter = RateLimiter(backend=TokenBucketBackend(rate=rate, burst_size=burst_size))

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            key = key_func(*args, **kwargs) if key_func else None

            with limiter.limit(key):
                return func(*args, **kwargs)

        return wrapper

    return decorator


class MultiRateLimiter:
    def __init__(self):
        self._limiters: dict[str, RateLimiter] = {}
        self._lock = threading.RLock()

    def register(self, name: str, backend: RateLimiterBackend):
        with self._lock:
            self._limiters[name] = RateLimiter(backend=backend)

    def register_token_bucket(self, name: str, rate: float, burst_size: int):
        self.register(name, TokenBucketBackend(rate=rate, burst_size=burst_size))

    def register_sliding_window(self, name: str, max_requests: int, window_seconds: float = 60.0):
        self.register(name, SlidingWindowBackend(max_requests, window_seconds))

    def get(self, name: str) -> RateLimiter | None:
        return self._limiters.get(name)

    def acquire(self, name: str, permits: int = 1) -> LimitResult:
        limiter = self.get(name)
        if limiter:
            return limiter.acquire(permits=permits)
        return LimitResult.ALLOWED

    def get_all_stats(self) -> dict[str, RateLimitStats]:
        return {name: limiter.get_stats() for name, limiter in self._limiters.items()}


__all__ = [
    "LimitResult",
    "RateLimitStats",
    "RateLimiterBackend",
    "TokenBucketBackend",
    "SlidingWindowBackend",
    "LeakyBucketBackend",
    "FixedWindowBackend",
    "RateLimiter",
    "rate_limit",
    "MultiRateLimiter",
]

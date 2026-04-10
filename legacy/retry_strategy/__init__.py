"""Retry Strategy - Advanced retry strategies with exponential backoff."""

from __future__ import annotations

import random
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class RetryResult(str, Enum):
    SUCCESS = "success"
    RETRY = "retry"
    GIVE_UP = "give_up"
    SKIP = "skip"


class RetryTrigger(str, Enum):
    EXCEPTION = "exception"
    RESULT = "result"
    TIMEOUT = "timeout"
    CUSTOM = "custom"


@dataclass
class RetryContext:
    attempt: int = 0
    max_attempts: int = 3
    last_error: Exception | None = None
    last_result: Any = None
    total_wait_time: float = 0.0
    start_time: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time

    @property
    def can_retry(self) -> bool:
        return self.attempt < self.max_attempts


@dataclass
class RetryStats:
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    retried_attempts: int = 0
    total_wait_time: float = 0.0
    avg_attempts_per_operation: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_attempts": self.total_attempts,
            "successful_attempts": self.successful_attempts,
            "failed_attempts": self.failed_attempts,
            "retried_attempts": self.retried_attempts,
            "total_wait_time": round(self.total_wait_time, 3),
            "avg_attempts_per_operation": round(self.avg_attempts_per_operation, 3),
        }


class RetryStrategy(ABC):
    @abstractmethod
    def should_retry(self, context: RetryContext) -> RetryResult:
        pass

    @abstractmethod
    def get_wait_time(self, context: RetryContext) -> float:
        pass

    def on_success(self, context: RetryContext):  # noqa: B027
        pass

    def on_failure(self, context: RetryContext):  # noqa: B027
        pass

    def on_retry(self, context: RetryContext):  # noqa: B027
        pass


class FixedDelayStrategy(RetryStrategy):
    def __init__(
        self,
        max_attempts: int = 3,
        delay_seconds: float = 1.0,
        retryable_exceptions: list[type] | None = None,
    ):
        self.max_attempts = max_attempts
        self.delay_seconds = delay_seconds
        self.retryable_exceptions = retryable_exceptions or [Exception]

    def should_retry(self, context: RetryContext) -> RetryResult:
        if context.last_error is None:
            return RetryResult.SUCCESS

        if not context.can_retry:
            return RetryResult.GIVE_UP

        if not any(
            isinstance(context.last_error, exc_type) for exc_type in self.retryable_exceptions
        ):
            return RetryResult.GIVE_UP

        return RetryResult.RETRY

    def get_wait_time(self, context: RetryContext) -> float:
        return self.delay_seconds


class ExponentialBackoffStrategy(RetryStrategy):
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: list[type] | None = None,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or [Exception]

    def should_retry(self, context: RetryContext) -> RetryResult:
        if context.last_error is None:
            return RetryResult.SUCCESS

        if not context.can_retry:
            return RetryResult.GIVE_UP

        if not any(
            isinstance(context.last_error, exc_type) for exc_type in self.retryable_exceptions
        ):
            return RetryResult.GIVE_UP

        return RetryResult.RETRY

    def get_wait_time(self, context: RetryContext) -> float:
        delay = self.base_delay * (self.multiplier**context.attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            delay = delay * (0.5 + random.random())

        return delay


class LinearBackoffStrategy(RetryStrategy):
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        increment: float = 1.0,
        max_delay: float = 60.0,
        retryable_exceptions: list[type] | None = None,
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.increment = increment
        self.max_delay = max_delay
        self.retryable_exceptions = retryable_exceptions or [Exception]

    def should_retry(self, context: RetryContext) -> RetryResult:
        if context.last_error is None:
            return RetryResult.SUCCESS

        if not context.can_retry:
            return RetryResult.GIVE_UP

        if not any(
            isinstance(context.last_error, exc_type) for exc_type in self.retryable_exceptions
        ):
            return RetryResult.GIVE_UP

        return RetryResult.RETRY

    def get_wait_time(self, context: RetryContext) -> float:
        delay = self.initial_delay + (context.attempt * self.increment)
        return min(delay, self.max_delay)


class FibonacciBackoffStrategy(RetryStrategy):
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        retryable_exceptions: list[type] | None = None,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retryable_exceptions = retryable_exceptions or [Exception]
        self._fib_cache = {0: 0, 1: 1}

    def _fibonacci(self, n: int) -> int:
        if n not in self._fib_cache:
            self._fib_cache[n] = self._fibonacci(n - 1) + self._fibonacci(n - 2)
        return self._fib_cache[n]

    def should_retry(self, context: RetryContext) -> RetryResult:
        if context.last_error is None:
            return RetryResult.SUCCESS

        if not context.can_retry:
            return RetryResult.GIVE_UP

        if not any(
            isinstance(context.last_error, exc_type) for exc_type in self.retryable_exceptions
        ):
            return RetryResult.GIVE_UP

        return RetryResult.RETRY

    def get_wait_time(self, context: RetryContext) -> float:
        delay = self.base_delay * self._fibonacci(context.attempt + 1)
        return min(delay, self.max_delay)


class AdaptiveStrategy(RetryStrategy):
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        success_threshold: int = 5,
        failure_threshold: int = 3,
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.success_threshold = success_threshold
        self.failure_threshold = failure_threshold

        self._consecutive_successes = 0
        self._consecutive_failures = 0
        self._current_delay = initial_delay
        self._lock = threading.Lock()

    def should_retry(self, context: RetryContext) -> RetryResult:
        if context.last_error is None:
            return RetryResult.SUCCESS

        if not context.can_retry:
            return RetryResult.GIVE_UP

        return RetryResult.RETRY

    def get_wait_time(self, context: RetryContext) -> float:
        with self._lock:
            return min(self._current_delay, self.max_delay)

    def on_success(self, context: RetryContext):
        with self._lock:
            self._consecutive_successes += 1
            self._consecutive_failures = 0

            if self._consecutive_successes >= self.success_threshold:
                self._current_delay = max(self.initial_delay, self._current_delay / 2)
                self._consecutive_successes = 0

    def on_failure(self, context: RetryContext):
        with self._lock:
            self._consecutive_failures += 1
            self._consecutive_successes = 0

            if self._consecutive_failures >= self.failure_threshold:
                self._current_delay = min(self.max_delay, self._current_delay * 2)
                self._consecutive_failures = 0


class RetryExecutor:
    def __init__(
        self,
        strategy: RetryStrategy | None = None,
        on_retry: Callable[[RetryContext], None] | None = None,
        on_failure: Callable[[RetryContext], None] | None = None,
        on_success: Callable[[RetryContext], None] | None = None,
    ):
        self.strategy = strategy or ExponentialBackoffStrategy()
        self.on_retry_callback = on_retry
        self.on_failure_callback = on_failure
        self.on_success_callback = on_success
        self._stats = RetryStats()
        self._lock = threading.Lock()

    def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        context = RetryContext(max_attempts=self._get_max_attempts())

        while True:
            context.attempt += 1

            with self._lock:
                self._stats.total_attempts += 1

            try:
                result = func(*args, **kwargs)
                context.last_result = result
                context.last_error = None

                retry_result = self.strategy.should_retry(context)

                if retry_result == RetryResult.SUCCESS:
                    with self._lock:
                        self._stats.successful_attempts += 1

                    self.strategy.on_success(context)

                    if self.on_success_callback:
                        self.on_success_callback(context)

                    return result

                if retry_result == RetryResult.SKIP:
                    return result

            except Exception as e:
                context.last_error = e

                retry_result = self.strategy.should_retry(context)

            if retry_result == RetryResult.GIVE_UP:
                with self._lock:
                    self._stats.failed_attempts += 1

                self.strategy.on_failure(context)

                if self.on_failure_callback:
                    self.on_failure_callback(context)

                if context.last_error:
                    raise context.last_error
                raise RuntimeError("Retry failed without specific error")

            if retry_result == RetryResult.RETRY:
                wait_time = self.strategy.get_wait_time(context)
                context.total_wait_time += wait_time

                with self._lock:
                    self._stats.retried_attempts += 1
                    self._stats.total_wait_time += wait_time

                self.strategy.on_retry(context)

                if self.on_retry_callback:
                    self.on_retry_callback(context)

                time.sleep(wait_time)

    def _get_max_attempts(self) -> int:
        if hasattr(self.strategy, "max_attempts"):
            return self.strategy.max_attempts
        return 3

    def get_stats(self) -> RetryStats:
        with self._lock:
            total_ops = self._stats.successful_attempts + self._stats.failed_attempts
            if total_ops > 0:
                self._stats.avg_attempts_per_operation = self._stats.total_attempts / total_ops
            return RetryStats(**dict(self._stats.__dict__.items()))


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    strategy: str = "exponential",
    retryable_exceptions: list[type] | None = None,
):
    if strategy == "exponential":
        retry_strategy = ExponentialBackoffStrategy(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            retryable_exceptions=retryable_exceptions,
        )
    elif strategy == "linear":
        retry_strategy = LinearBackoffStrategy(
            max_attempts=max_attempts,
            initial_delay=base_delay,
            max_delay=max_delay,
            retryable_exceptions=retryable_exceptions,
        )
    elif strategy == "fixed":
        retry_strategy = FixedDelayStrategy(
            max_attempts=max_attempts,
            delay_seconds=base_delay,
            retryable_exceptions=retryable_exceptions,
        )
    else:
        retry_strategy = FibonacciBackoffStrategy(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            retryable_exceptions=retryable_exceptions,
        )

    executor = RetryExecutor(strategy=retry_strategy)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            return executor.execute(func, *args, **kwargs)

        wrapper.retry_stats = executor.get_stats
        return wrapper

    return decorator


__all__ = [
    "RetryResult",
    "RetryTrigger",
    "RetryContext",
    "RetryStats",
    "RetryStrategy",
    "FixedDelayStrategy",
    "ExponentialBackoffStrategy",
    "LinearBackoffStrategy",
    "FibonacciBackoffStrategy",
    "AdaptiveStrategy",
    "RetryExecutor",
    "retry",
]

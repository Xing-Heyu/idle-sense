"""Timeout Manager - Task timeout management with multiple strategies."""

from __future__ import annotations

import signal
import threading
import time
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class TimeoutAction(str, Enum):
    RAISE = "raise"
    RETURN_DEFAULT = "return_default"
    CALLBACK = "callback"
    CANCEL = "cancel"


class TimeoutState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class TimeoutContext:
    timeout_id: str
    timeout_seconds: float
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    state: TimeoutState = TimeoutState.PENDING
    result: Any = None
    error: Exception | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def elapsed_time(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def remaining_time(self) -> float:
        return max(0, self.timeout_seconds - self.elapsed_time)

    @property
    def is_expired(self) -> bool:
        return self.elapsed_time >= self.timeout_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeout_id": self.timeout_id,
            "timeout_seconds": self.timeout_seconds,
            "elapsed_time": round(self.elapsed_time, 3),
            "remaining_time": round(self.remaining_time, 3),
            "state": self.state.value,
            "is_expired": self.is_expired,
        }


class TimeoutError(Exception):
    def __init__(self, message: str, context: TimeoutContext | None = None):
        super().__init__(message)
        self.context = context


@dataclass
class TimeoutStats:
    total_timeouts: int = 0
    completed_timeouts: int = 0
    triggered_timeouts: int = 0
    cancelled_timeouts: int = 0
    avg_execution_time: float = 0.0
    avg_timeout_ratio: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_timeouts": self.total_timeouts,
            "completed_timeouts": self.completed_timeouts,
            "triggered_timeouts": self.triggered_timeouts,
            "cancelled_timeouts": self.cancelled_timeouts,
            "avg_execution_time": round(self.avg_execution_time, 3),
            "avg_timeout_ratio": round(self.avg_timeout_ratio, 3),
        }


class TimeoutManager:
    def __init__(self):
        self._timeouts: dict[str, TimeoutContext] = {}
        self._timers: dict[str, threading.Timer] = {}
        self._callbacks: dict[str, Callable] = {}
        self._stats = TimeoutStats()
        self._execution_times: list[float] = []
        self._lock = threading.RLock()

    def register(
        self,
        timeout_seconds: float,
        callback: Callable | None = None,
        timeout_id: str | None = None,
    ) -> TimeoutContext:
        import uuid

        tid = timeout_id or str(uuid.uuid4())

        context = TimeoutContext(
            timeout_id=tid, timeout_seconds=timeout_seconds, state=TimeoutState.PENDING
        )

        with self._lock:
            self._timeouts[tid] = context
            self._stats.total_timeouts += 1

            if callback:
                self._callbacks[tid] = callback

        return context

    def start(self, timeout_id: str) -> bool:
        with self._lock:
            context = self._timeouts.get(timeout_id)
            if not context or context.state != TimeoutState.PENDING:
                return False

            context.state = TimeoutState.RUNNING
            context.start_time = time.time()

            timer = threading.Timer(
                context.timeout_seconds, self._handle_timeout, args=(timeout_id,)
            )
            timer.daemon = True
            timer.start()

            self._timers[timeout_id] = timer

        return True

    def complete(self, timeout_id: str, result: Any = None) -> bool:
        with self._lock:
            context = self._timeouts.get(timeout_id)
            if not context or context.state != TimeoutState.RUNNING:
                return False

            timer = self._timers.pop(timeout_id, None)
            if timer:
                timer.cancel()

            context.state = TimeoutState.COMPLETED
            context.end_time = time.time()
            context.result = result

            self._stats.completed_timeouts += 1
            self._execution_times.append(context.elapsed_time)
            if len(self._execution_times) > 100:
                self._execution_times = self._execution_times[-100:]
            self._stats.avg_execution_time = sum(self._execution_times) / len(self._execution_times)

            self._update_timeout_ratio()

        return True

    def cancel(self, timeout_id: str) -> bool:
        with self._lock:
            context = self._timeouts.get(timeout_id)
            if not context or context.state not in (TimeoutState.PENDING, TimeoutState.RUNNING):
                return False

            timer = self._timers.pop(timeout_id, None)
            if timer:
                timer.cancel()

            context.state = TimeoutState.CANCELLED
            context.end_time = time.time()

            self._stats.cancelled_timeouts += 1

        return True

    def _handle_timeout(self, timeout_id: str):
        with self._lock:
            context = self._timeouts.get(timeout_id)
            if not context or context.state != TimeoutState.RUNNING:
                return

            context.state = TimeoutState.TIMEOUT
            context.end_time = time.time()

            self._stats.triggered_timeouts += 1
            self._update_timeout_ratio()

            callback = self._callbacks.get(timeout_id)

        if callback:
            with suppress(Exception):
                callback(context)

    def _update_timeout_ratio(self):
        total = self._stats.completed_timeouts + self._stats.triggered_timeouts
        if total > 0:
            self._stats.avg_timeout_ratio = self._stats.triggered_timeouts / total

    def get_context(self, timeout_id: str) -> TimeoutContext | None:
        return self._timeouts.get(timeout_id)

    def get_remaining_time(self, timeout_id: str) -> float:
        context = self._timeouts.get(timeout_id)
        if context:
            return context.remaining_time
        return 0.0

    def is_expired(self, timeout_id: str) -> bool:
        context = self._timeouts.get(timeout_id)
        return context.is_expired if context else True

    def get_stats(self) -> TimeoutStats:
        with self._lock:
            return TimeoutStats(**dict(self._stats.__dict__.items()))

    def clear_completed(self, max_age_seconds: float = 3600) -> int:
        now = time.time()
        to_remove = []

        with self._lock:
            for tid, context in self._timeouts.items():
                if (
                    context.state
                    in (TimeoutState.COMPLETED, TimeoutState.TIMEOUT, TimeoutState.CANCELLED)
                    and context.end_time
                    and (now - context.end_time) > max_age_seconds
                ):
                    to_remove.append(tid)

            for tid in to_remove:
                del self._timeouts[tid]
                self._callbacks.pop(tid, None)

        return len(to_remove)


class TimeoutExecutor:
    def __init__(
        self,
        default_timeout: float = 30.0,
        action: TimeoutAction = TimeoutAction.RAISE,
        default_value: Any = None,
        on_timeout: Callable[[TimeoutContext], None] | None = None,
    ):
        self.default_timeout = default_timeout
        self.action = action
        self.default_value = default_value
        self.on_timeout = on_timeout
        self._manager = TimeoutManager()

    def execute(self, func: Callable[..., T], *args, timeout: float | None = None, **kwargs) -> T:
        timeout_seconds = timeout or self.default_timeout

        context = self._manager.register(timeout_seconds, callback=self.on_timeout)

        result = [None]
        error = [None]
        completed = threading.Event()

        def target():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                error[0] = e
            finally:
                completed.set()

        self._manager.start(context.timeout_id)

        thread = threading.Thread(target=target, daemon=True)
        thread.start()

        finished = completed.wait(timeout=timeout_seconds)

        if finished:
            self._manager.complete(context.timeout_id, result[0])
            if error[0]:
                raise error[0]
            return result[0]

        self._manager._handle_timeout(context.timeout_id)

        if self.action == TimeoutAction.RAISE:
            raise TimeoutError(f"Operation timed out after {timeout_seconds} seconds", context)
        elif self.action == TimeoutAction.RETURN_DEFAULT:
            return self.default_value
        elif self.action == TimeoutAction.CALLBACK:
            if self.on_timeout:
                self.on_timeout(context)
            return self.default_value

        return self.default_value

    def get_stats(self) -> TimeoutStats:
        return self._manager.get_stats()


def timeout(seconds: float, action: TimeoutAction = TimeoutAction.RAISE, default: Any = None):
    executor = TimeoutExecutor(default_timeout=seconds, action=action, default_value=default)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            return executor.execute(func, *args, **kwargs)

        wrapper.timeout_stats = executor.get_stats
        return wrapper

    return decorator


@contextmanager
def timeout_context(seconds: float, message: str = "Operation timed out"):
    if threading.current_thread() is threading.main_thread():

        def timeout_handler(signum, frame):
            raise TimeoutError(message)

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, seconds)

        try:
            yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        manager = TimeoutManager()
        context = manager.register(seconds)
        manager.start(context.timeout_id)

        try:
            yield context
            if context.is_expired:
                raise TimeoutError(message, context)
        finally:
            manager.cancel(context.timeout_id)


class CompositeTimeout:
    def __init__(self):
        self._timeouts: dict[str, float] = {}
        self._manager = TimeoutManager()
        self._lock = threading.Lock()

    def add(self, name: str, timeout_seconds: float):
        with self._lock:
            self._timeouts[name] = timeout_seconds

    def remove(self, name: str):
        with self._lock:
            self._timeouts.pop(name, None)

    def start_all(self) -> dict[str, TimeoutContext]:
        contexts = {}
        with self._lock:
            for name, seconds in self._timeouts.items():
                context = self._manager.register(seconds)
                self._manager.start(context.timeout_id)
                contexts[name] = context
        return contexts

    def check_all(self) -> dict[str, bool]:
        results = {}
        with self._lock:
            for name in self._timeouts:
                contexts = self._manager._timeouts
                for ctx in contexts.values():
                    if ctx.metadata.get("name") == name:
                        results[name] = ctx.is_expired
                        break
        return results

    def any_expired(self) -> bool:
        return any(self.check_all().values())

    def all_expired(self) -> bool:
        results = self.check_all()
        return all(results.values()) if results else False


__all__ = [
    "TimeoutAction",
    "TimeoutState",
    "TimeoutContext",
    "TimeoutError",
    "TimeoutStats",
    "TimeoutManager",
    "TimeoutExecutor",
    "timeout",
    "timeout_context",
    "CompositeTimeout",
]

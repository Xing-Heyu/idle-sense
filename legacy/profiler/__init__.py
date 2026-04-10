"""Performance Profiler - Comprehensive profiling and performance analysis."""

from __future__ import annotations

import cProfile
import functools
import io
import pstats
import statistics
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable)


class ProfileLevel(str, Enum):
    FUNCTION = "function"
    BLOCK = "block"
    LINE = "line"
    MEMORY = "memory"


@dataclass
class FunctionProfile:
    name: str
    calls: int = 0
    total_time: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    avg_time: float = 0.0
    total_memory: int = 0
    timestamps: list[float] = field(default_factory=list)

    @property
    def self_time(self) -> float:
        return self.total_time

    def record(self, duration: float, memory: int = 0):
        self.calls += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.avg_time = self.total_time / self.calls
        self.total_memory += memory
        self.timestamps.append(time.time())

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "calls": self.calls,
            "total_time": round(self.total_time, 6),
            "min_time": round(self.min_time, 6) if self.min_time != float("inf") else 0,
            "max_time": round(self.max_time, 6),
            "avg_time": round(self.avg_time, 6),
            "total_memory": self.total_memory,
        }


@dataclass
class BlockProfile:
    name: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    memory_before: int = 0
    memory_after: int = 0
    memory_delta: int = 0
    children: list[BlockProfile] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        return self.duration * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "duration_ms": round(self.duration_ms, 3),
            "memory_delta_kb": self.memory_delta / 1024,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class ProfileReport:
    session_id: str
    start_time: float
    end_time: float = 0.0
    function_profiles: dict[str, FunctionProfile] = field(default_factory=dict)
    block_profiles: list[BlockProfile] = field(default_factory=list)
    memory_snapshots: list[dict[str, Any]] = field(default_factory=list)
    custom_metrics: dict[str, list[float]] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time if self.end_time else 0

    def get_hotspots(self, top_n: int = 10) -> list[FunctionProfile]:
        sorted_profiles = sorted(
            self.function_profiles.values(), key=lambda p: p.total_time, reverse=True
        )
        return sorted_profiles[:top_n]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "duration_seconds": round(self.duration, 3),
            "function_count": len(self.function_profiles),
            "hotspots": [p.to_dict() for p in self.get_hotspots()],
            "blocks": [b.to_dict() for b in self.block_profiles],
            "custom_metrics": {
                k: {
                    "count": len(v),
                    "avg": statistics.mean(v) if v else 0,
                    "min": min(v) if v else 0,
                    "max": max(v) if v else 0,
                }
                for k, v in self.custom_metrics.items()
            },
        }


class MemoryTracker:
    def __init__(self):
        self._enabled = False
        self._snapshots: list[dict[str, Any]] = []

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    def snapshot(self, label: str = "") -> dict[str, Any]:
        snapshot = {"timestamp": time.time(), "label": label, "memory_mb": 0}

        try:
            import psutil

            process = psutil.Process()
            snapshot["memory_mb"] = process.memory_info().rss / 1024 / 1024
        except ImportError:
            pass

        if self._enabled:
            self._snapshots.append(snapshot)

        return snapshot

    def get_memory_delta(self, start_snapshot: dict, end_snapshot: dict) -> int:
        return int(
            (end_snapshot.get("memory_mb", 0) - start_snapshot.get("memory_mb", 0)) * 1024 * 1024
        )

    def clear(self):
        self._snapshots.clear()


class Profiler:
    _instance: Profiler | None = None
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
        self._profiles: dict[str, FunctionProfile] = {}
        self._active_blocks: dict[str, BlockProfile] = {}
        self._block_stack: list[str] = []
        self._reports: dict[str, ProfileReport] = {}
        self._current_session: str | None = None
        self._memory_tracker = MemoryTracker()
        self._profile_lock = threading.RLock()

    def start_session(self, session_id: str | None = None) -> str:
        session_id = session_id or f"session_{int(time.time() * 1000)}"

        with self._profile_lock:
            self._reports[session_id] = ProfileReport(session_id=session_id, start_time=time.time())
            self._current_session = session_id

        return session_id

    def end_session(self, session_id: str | None = None) -> ProfileReport | None:
        session_id = session_id or self._current_session

        if not session_id or session_id not in self._reports:
            return None

        with self._profile_lock:
            report = self._reports[session_id]
            report.end_time = time.time()
            report.function_profiles = dict(self._profiles)
            report.memory_snapshots = self._memory_tracker._snapshots.copy()

            if session_id == self._current_session:
                self._current_session = None

        return report

    def profile_function(
        self, name: str | None = None, track_memory: bool = False
    ) -> Callable[[F], F]:
        def decorator(func: F) -> F:
            profile_name = name or f"{func.__module__}.{func.__qualname__}"

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                start_memory = {}

                if track_memory:
                    start_memory = self._memory_tracker.snapshot()

                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.perf_counter() - start_time
                    memory_delta = 0

                    if track_memory:
                        end_memory = self._memory_tracker.snapshot()
                        memory_delta = self._memory_tracker.get_memory_delta(
                            start_memory, end_memory
                        )

                    with self._profile_lock:
                        if profile_name not in self._profiles:
                            self._profiles[profile_name] = FunctionProfile(name=profile_name)
                        self._profiles[profile_name].record(duration, memory_delta)

            return wrapper

        return decorator

    @contextmanager
    def profile_block(self, name: str, track_memory: bool = False):
        block_id = f"{name}_{id(threading.current_thread())}"
        start_time = time.perf_counter()
        start_memory = {}

        if track_memory:
            start_memory = self._memory_tracker.snapshot()

        block = BlockProfile(name=name, start_time=start_time)

        with self._profile_lock:
            self._active_blocks[block_id] = block
            self._block_stack.append(block_id)

        try:
            yield block
        finally:
            end_time = time.perf_counter()
            end_memory = {}

            if track_memory:
                end_memory = self._memory_tracker.snapshot()

            with self._profile_lock:
                if block_id in self._active_blocks:
                    block = self._active_blocks.pop(block_id)
                    block.end_time = end_time
                    block.duration = end_time - start_time

                    if track_memory:
                        block.memory_delta = self._memory_tracker.get_memory_delta(
                            start_memory, end_memory
                        )

                    if self._block_stack and self._block_stack[-1] == block_id:
                        self._block_stack.pop()

                    if self._current_session and self._current_session in self._reports:
                        self._reports[self._current_session].block_profiles.append(block)

    def record_metric(self, name: str, value: float):
        with self._profile_lock:
            if self._current_session and self._current_session in self._reports:
                report = self._reports[self._current_session]
                if name not in report.custom_metrics:
                    report.custom_metrics[name] = []
                report.custom_metrics[name].append(value)

    def get_function_stats(self, name: str) -> FunctionProfile | None:
        return self._profiles.get(name)

    def get_all_stats(self) -> dict[str, FunctionProfile]:
        return dict(self._profiles)

    def clear(self):
        with self._profile_lock:
            self._profiles.clear()
            self._active_blocks.clear()
            self._block_stack.clear()
            self._reports.clear()
            self._memory_tracker.clear()

    def cprofile(self, sort_by: str = "cumulative") -> cProfile.Profile:
        return cProfile.Profile(sort=sort_by)

    def profile_code(self, code: str, globals_dict: dict | None = None) -> str:
        from src.infrastructure.sandbox.security import CodeValidator

        validator = CodeValidator()
        is_valid, errors = validator.validate(code)
        if not is_valid:
            return f"代码安全检查失败: {'; '.join(errors)}"

        pr = cProfile.Profile()
        pr.enable()

        try:
            safe_globals = {"__builtins__": {}}
            if globals_dict:
                safe_globals.update(globals_dict)
            exec(code, safe_globals)
        except Exception as e:
            return f"Error: {e}"
        finally:
            pr.disable()

        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
        ps.print_stats()

        return s.getvalue()


profiler = Profiler()


def profile(name: str | None = None, track_memory: bool = False):
    return profiler.profile_function(name, track_memory)


def profile_block(name: str, track_memory: bool = False):
    return profiler.profile_block(name, track_memory)


class PerformanceAnalyzer:
    def __init__(self, report: ProfileReport):
        self.report = report

    def get_bottlenecks(self, threshold_ms: float = 100.0) -> list[dict[str, Any]]:
        bottlenecks = []

        for name, profile in self.report.function_profiles.items():
            if profile.avg_time * 1000 >= threshold_ms:
                bottlenecks.append(
                    {
                        "function": name,
                        "avg_time_ms": profile.avg_time * 1000,
                        "calls": profile.calls,
                        "total_time_ms": profile.total_time * 1000,
                    }
                )

        return sorted(bottlenecks, key=lambda x: x["total_time_ms"], reverse=True)

    def get_memory_leaks(self, threshold_mb: float = 10.0) -> list[dict[str, Any]]:
        leaks = []

        for block in self.report.block_profiles:
            if block.memory_delta / 1024 / 1024 >= threshold_mb:
                leaks.append(
                    {"block": block.name, "memory_delta_mb": block.memory_delta / 1024 / 1024}
                )

        return leaks

    def get_call_patterns(self) -> dict[str, Any]:
        patterns = {"most_called": None, "slowest": None, "most_memory": None}

        if not self.report.function_profiles:
            return patterns

        profiles = list(self.report.function_profiles.values())

        patterns["most_called"] = max(profiles, key=lambda p: p.calls).name
        patterns["slowest"] = max(profiles, key=lambda p: p.avg_time).name
        patterns["most_memory"] = max(profiles, key=lambda p: p.total_memory).name

        return patterns

    def generate_report(self) -> str:
        lines = [
            "# Performance Analysis Report",
            f"\n**Session:** {self.report.session_id}",
            f"**Duration:** {self.report.duration:.3f} seconds",
            f"**Functions Profiled:** {len(self.report.function_profiles)}",
            "",
            "## Top Hotspots",
            "",
            "| Function | Calls | Total Time (ms) | Avg Time (ms) |",
            "|----------|-------|-----------------|---------------|",
        ]

        for profile in self.report.get_hotspots(10):
            lines.append(
                f"| {profile.name} | {profile.calls} | "
                f"{profile.total_time * 1000:.3f} | {profile.avg_time * 1000:.3f} |"
            )

        bottlenecks = self.get_bottlenecks()
        if bottlenecks:
            lines.extend(["", "## Bottlenecks (>100ms avg)", ""])
            for b in bottlenecks[:5]:
                lines.append(
                    f"- **{b['function']}**: {b['avg_time_ms']:.1f}ms avg ({b['calls']} calls)"
                )

        return "\n".join(lines)


__all__ = [
    "ProfileLevel",
    "FunctionProfile",
    "BlockProfile",
    "ProfileReport",
    "MemoryTracker",
    "Profiler",
    "profiler",
    "profile",
    "profile_block",
    "PerformanceAnalyzer",
]

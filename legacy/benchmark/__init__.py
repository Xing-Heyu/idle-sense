"""
Performance Benchmark Suite.

This module provides comprehensive benchmarking tools for measuring
system performance and identifying bottlenecks.

Usage:
    python -m benchmark run --suite all
    python -m benchmark compare --baseline v1.0.0
"""

import asyncio
import gc
import json
import os
import statistics
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str
    iterations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    std_dev: float
    memory_peak_mb: float
    memory_avg_mb: float
    success: bool
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ops_per_second(self) -> float:
        """Operations per second."""
        if self.avg_time > 0:
            return 1.0 / self.avg_time
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time": self.total_time,
            "avg_time": self.avg_time,
            "min_time": self.min_time,
            "max_time": self.max_time,
            "std_dev": self.std_dev,
            "memory_peak_mb": self.memory_peak_mb,
            "memory_avg_mb": self.memory_avg_mb,
            "success": self.success,
            "error": self.error,
            "ops_per_second": self.ops_per_second,
            "metadata": self.metadata,
        }


@dataclass
class BenchmarkSuite:
    """A suite of benchmarks."""

    name: str
    description: str
    benchmarks: list[BenchmarkResult] = field(default_factory=list)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "benchmarks": [b.to_dict() for b in self.benchmarks],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_benchmarks": len(self.benchmarks),
            "passed": sum(1 for b in self.benchmarks if b.success),
            "failed": sum(1 for b in self.benchmarks if not b.success),
        }


class Benchmark:
    """Base class for benchmarks."""

    def __init__(
        self, name: str, iterations: int = 100, warmup: int = 10, measure_memory: bool = True
    ):
        self.name = name
        self.iterations = iterations
        self.warmup = warmup
        self.measure_memory = measure_memory

    def setup(self):
        """Setup before benchmark. Override this method."""
        pass

    def teardown(self):
        """Teardown after benchmark. Override this method."""
        pass

    def run_iteration(self) -> Any:
        """Run a single iteration. Override this method."""
        raise NotImplementedError("Subclasses must implement run_iteration()")

    def run(self) -> BenchmarkResult:
        """Run the benchmark."""
        try:
            self.setup()

            for _ in range(self.warmup):
                self.run_iteration()

            gc.collect()

            times = []
            memory_samples = []

            if self.measure_memory:
                tracemalloc.start()

            start_total = time.perf_counter()

            for _ in range(self.iterations):
                gc.collect()

                start = time.perf_counter()
                self.run_iteration()
                end = time.perf_counter()

                times.append(end - start)

                if self.measure_memory:
                    current, peak = tracemalloc.get_traced_memory()
                    memory_samples.append(current / 1024 / 1024)

            end_total = time.perf_counter()

            if self.measure_memory:
                tracemalloc.stop()

            result = BenchmarkResult(
                name=self.name,
                iterations=self.iterations,
                total_time=end_total - start_total,
                avg_time=statistics.mean(times),
                min_time=min(times),
                max_time=max(times),
                std_dev=statistics.stdev(times) if len(times) > 1 else 0,
                memory_peak_mb=max(memory_samples) if memory_samples else 0,
                memory_avg_mb=statistics.mean(memory_samples) if memory_samples else 0,
                success=True,
            )

            self.teardown()
            return result

        except Exception as e:
            return BenchmarkResult(
                name=self.name,
                iterations=0,
                total_time=0,
                avg_time=0,
                min_time=0,
                max_time=0,
                std_dev=0,
                memory_peak_mb=0,
                memory_avg_mb=0,
                success=False,
                error=str(e),
            )


class BenchmarkRunner:
    """Runner for executing benchmark suites."""

    def __init__(self, output_dir: str = "benchmark_results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def run_suite(self, name: str, description: str, benchmarks: list[Benchmark]) -> BenchmarkSuite:
        """Run a suite of benchmarks."""
        suite = BenchmarkSuite(name=name, description=description, started_at=time.time())

        print(f"\n{'='*60}")
        print(f"Running benchmark suite: {name}")
        print(f"{'='*60}\n")

        for benchmark in benchmarks:
            print(f"Running: {benchmark.name}...", end=" ")
            result = benchmark.run()
            suite.benchmarks.append(result)

            if result.success:
                print(f"✓ {result.avg_time*1000:.3f}ms ({result.ops_per_second:.1f} ops/s)")
            else:
                print(f"✗ {result.error}")

        suite.completed_at = time.time()

        return suite

    def save_results(self, suite: BenchmarkSuite, filename: Optional[str] = None):
        """Save benchmark results to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{suite.name}_{timestamp}.json"

        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w") as f:
            json.dump(suite.to_dict(), f, indent=2)

        print(f"\nResults saved to: {filepath}")

    def compare_suites(self, baseline: BenchmarkSuite, current: BenchmarkSuite) -> dict[str, Any]:
        """Compare two benchmark suites."""
        comparison = {"baseline": baseline.name, "current": current.name, "comparisons": []}

        baseline_results = {b.name: b for b in baseline.benchmarks}
        current_results = {b.name: b for b in current.benchmarks}

        for name, current_result in current_results.items():
            if name in baseline_results:
                baseline_result = baseline_results[name]

                if baseline_result.avg_time > 0:
                    change = (
                        (current_result.avg_time - baseline_result.avg_time)
                        / baseline_result.avg_time
                        * 100
                    )
                else:
                    change = 0

                comparison["comparisons"].append(
                    {
                        "name": name,
                        "baseline_avg_ms": baseline_result.avg_time * 1000,
                        "current_avg_ms": current_result.avg_time * 1000,
                        "change_percent": change,
                        "improved": change < 0,
                    }
                )

        return comparison


# Predefined Benchmarks


class IdleDetectionBenchmark(Benchmark):
    """Benchmark for idle detection."""

    def __init__(self, iterations: int = 1000):
        super().__init__(name="idle_detection", iterations=iterations, warmup=100)

    def setup(self):
        from idle_sense import get_system_status, is_idle

        self.is_idle = is_idle
        self.get_status = get_system_status

    def run_iteration(self):
        self.is_idle()
        self.get_status()


class TaskSubmissionBenchmark(Benchmark):
    """Benchmark for task submission."""

    def __init__(self, iterations: int = 100):
        super().__init__(name="task_submission", iterations=iterations, warmup=10)

    def setup(self):
        from storage import MemoryStorage, TaskInfo

        self.storage = MemoryStorage()
        self.TaskInfo = TaskInfo
        self.task_count = 0

    def run_iteration(self):
        task = self.TaskInfo(task_id=0, code="result = 1 + 1")
        asyncio.run(self.storage.store_task(task))
        self.task_count += 1


class SandboxExecutionBenchmark(Benchmark):
    """Benchmark for sandbox code execution."""

    def __init__(self, iterations: int = 50):
        super().__init__(
            name="sandbox_execution", iterations=iterations, warmup=5, measure_memory=True
        )

    def setup(self):
        from sandbox_v2 import SandboxLevel, SecureSandbox

        self.sandbox = SecureSandbox(level=SandboxLevel.BASIC)
        self.code = """
data = list(range(1000))
result = sum(data)
__result__ = result
"""

    def run_iteration(self):
        self.sandbox.execute(self.code)


class SchedulerBenchmark(Benchmark):
    """Benchmark for scheduler decision making."""

    def __init__(self, iterations: int = 100):
        super().__init__(name="scheduler_decision", iterations=iterations, warmup=20)

    def setup(self):
        from src.infrastructure.scheduler.scheduler import SimpleScheduler

        self.scheduler = SimpleScheduler()

        self.nodes = [
            {
                "node_id": f"node-{i}",
                "capacity": {"cpu": 4.0, "memory": 8192},
                "available_resources": {"cpu": 3.0, "memory": 6000},
                "is_idle": True,
                "is_available": True,
                "cpu_usage": 20.0,
                "memory_usage": 30.0,
            }
            for i in range(10)
        ]

        self.task = {
            "resources": {"cpu": 1.0, "memory": 512},
            "user_id": "test_user",
        }

    def run_iteration(self):
        self.scheduler.schedule(self.task, self.nodes)


def run_all_benchmarks(output_dir: str = "benchmark_results") -> BenchmarkSuite:
    """Run all predefined benchmarks."""
    runner = BenchmarkRunner(output_dir)

    benchmarks = [
        IdleDetectionBenchmark(iterations=500),
        TaskSubmissionBenchmark(iterations=200),
        SandboxExecutionBenchmark(iterations=100),
        SchedulerBenchmark(iterations=500),
    ]

    suite = runner.run_suite(
        name="idle_accelerator_full",
        description="Full benchmark suite for idle-accelerator",
        benchmarks=benchmarks,
    )

    runner.save_results(suite)

    return suite


if __name__ == "__main__":
    run_all_benchmarks()

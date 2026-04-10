"""Resource Estimator - Estimates task resource requirements."""

from __future__ import annotations

import statistics
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResourceType(str, Enum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    GPU = "gpu"
    TIME = "time"


@dataclass
class ResourceEstimate:
    cpu_cores: float = 1.0
    memory_mb: float = 256.0
    disk_mb: float = 0.0
    network_mbps: float = 0.0
    gpu_count: int = 0
    estimated_duration_seconds: float = 60.0
    confidence: float = 0.5
    based_on_samples: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "disk_mb": self.disk_mb,
            "network_mbps": self.network_mbps,
            "gpu_count": self.gpu_count,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "confidence": self.confidence,
            "based_on_samples": self.based_on_samples,
        }

    def __add__(self, other: ResourceEstimate) -> ResourceEstimate:
        return ResourceEstimate(
            cpu_cores=self.cpu_cores + other.cpu_cores,
            memory_mb=self.memory_mb + other.memory_mb,
            disk_mb=self.disk_mb + other.disk_mb,
            network_mbps=self.network_mbps + other.network_mbps,
            gpu_count=max(self.gpu_count, other.gpu_count),
            estimated_duration_seconds=self.estimated_duration_seconds
            + other.estimated_duration_seconds,
            confidence=min(self.confidence, other.confidence),
            based_on_samples=self.based_on_samples + other.based_on_samples,
        )

    def __mul__(self, factor: float) -> ResourceEstimate:
        return ResourceEstimate(
            cpu_cores=self.cpu_cores * factor,
            memory_mb=self.memory_mb * factor,
            disk_mb=self.disk_mb * factor,
            network_mbps=self.network_mbps * factor,
            gpu_count=self.gpu_count,
            estimated_duration_seconds=self.estimated_duration_seconds * factor,
            confidence=self.confidence,
            based_on_samples=self.based_on_samples,
        )


@dataclass
class TaskMetrics:
    task_type: str
    input_size: int
    actual_cpu: float
    actual_memory: float
    actual_disk: float
    actual_network: float
    actual_duration: float
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    node_id: str | None = None


class EstimationStrategy(ABC):
    @abstractmethod
    def estimate(
        self, task_type: str, input_size: int, historical_data: list[TaskMetrics]
    ) -> ResourceEstimate:
        pass


class LinearRegressionEstimator(EstimationStrategy):
    def estimate(
        self, task_type: str, input_size: int, historical_data: list[TaskMetrics]
    ) -> ResourceEstimate:
        if not historical_data:
            return ResourceEstimate()

        data = [(m.input_size, m) for m in historical_data if m.success]

        if len(data) < 2:
            avg = self._compute_average([m for _, m in data])
            avg.based_on_samples = len(data)
            return avg

        sizes = [d[0] for d in data]
        durations = [d[1].actual_duration for d in data]
        memories = [d[1].actual_memory for d in data]
        cpus = [d[1].actual_cpu for d in data]

        duration_slope, duration_intercept = self._linear_regression(sizes, durations)
        memory_slope, memory_intercept = self._linear_regression(sizes, memories)
        cpu_slope, cpu_intercept = self._linear_regression(sizes, cpus)

        estimated_duration = max(1, duration_slope * input_size + duration_intercept)
        estimated_memory = max(64, memory_slope * input_size + memory_intercept)
        estimated_cpu = max(0.1, cpu_slope * input_size + cpu_intercept)

        confidence = min(1.0, len(data) / 10.0)

        return ResourceEstimate(
            cpu_cores=estimated_cpu,
            memory_mb=estimated_memory,
            estimated_duration_seconds=estimated_duration,
            confidence=confidence,
            based_on_samples=len(data),
        )

    def _compute_average(self, metrics: list[TaskMetrics]) -> ResourceEstimate:
        if not metrics:
            return ResourceEstimate()

        return ResourceEstimate(
            cpu_cores=statistics.mean(m.actual_cpu for m in metrics),
            memory_mb=statistics.mean(m.actual_memory for m in metrics),
            disk_mb=statistics.mean(m.actual_disk for m in metrics),
            network_mbps=statistics.mean(m.actual_network for m in metrics),
            estimated_duration_seconds=statistics.mean(m.actual_duration for m in metrics),
            confidence=0.5,
        )

    def _linear_regression(self, x: list[float], y: list[float]) -> tuple[float, float]:
        n = len(x)
        if n == 0:
            return 0, 0

        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_xx = sum(xi * xi for xi in x)

        denominator = n * sum_xx - sum_x * sum_x
        if denominator == 0:
            return 0, sum_y / n

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n

        return slope, intercept


class PercentileEstimator(EstimationStrategy):
    def __init__(self, percentile: float = 90):
        self.percentile = percentile

    def estimate(
        self, task_type: str, input_size: int, historical_data: list[TaskMetrics]
    ) -> ResourceEstimate:
        if not historical_data:
            return ResourceEstimate()

        success_data = [m for m in historical_data if m.success]
        if not success_data:
            return ResourceEstimate()

        similar_size = [
            m for m in success_data if abs(m.input_size - input_size) <= input_size * 0.5
        ]

        data = similar_size if similar_size else success_data

        return ResourceEstimate(
            cpu_cores=self._percentile([m.actual_cpu for m in data]),
            memory_mb=self._percentile([m.actual_memory for m in data]),
            disk_mb=self._percentile([m.actual_disk for m in data]),
            network_mbps=self._percentile([m.actual_network for m in data]),
            estimated_duration_seconds=self._percentile([m.actual_duration for m in data]),
            confidence=min(1.0, len(data) / 5.0),
            based_on_samples=len(data),
        )

    def _percentile(self, values: list[float]) -> float:
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * self.percentile / 100)
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]


class WeightedAverageEstimator(EstimationStrategy):
    def __init__(self, decay_factor: float = 0.9):
        self.decay_factor = decay_factor

    def estimate(
        self, task_type: str, input_size: int, historical_data: list[TaskMetrics]
    ) -> ResourceEstimate:
        if not historical_data:
            return ResourceEstimate()

        success_data = sorted(
            [m for m in historical_data if m.success], key=lambda m: m.timestamp, reverse=True
        )

        if not success_data:
            return ResourceEstimate()

        weights = []
        for i, m in enumerate(success_data):
            size_weight = 1.0 / (1 + abs(m.input_size - input_size) / max(1, input_size))
            time_weight = self.decay_factor**i
            weights.append(size_weight * time_weight)

        total_weight = sum(weights)

        def weighted_avg(values: list[float]) -> float:
            return sum(v * w for v, w in zip(values, weights)) / total_weight

        return ResourceEstimate(
            cpu_cores=weighted_avg([m.actual_cpu for m in success_data]),
            memory_mb=weighted_avg([m.actual_memory for m in success_data]),
            disk_mb=weighted_avg([m.actual_disk for m in success_data]),
            network_mbps=weighted_avg([m.actual_network for m in success_data]),
            estimated_duration_seconds=weighted_avg([m.actual_duration for m in success_data]),
            confidence=min(1.0, len(success_data) / 10.0),
            based_on_samples=len(success_data),
        )


class ResourceEstimator:
    def __init__(self, strategy: EstimationStrategy | None = None, max_history: int = 1000):
        self.strategy = strategy or LinearRegressionEstimator()
        self.max_history = max_history
        self._history: dict[str, list[TaskMetrics]] = {}
        self._lock = threading.RLock()
        self._defaults: dict[str, ResourceEstimate] = {}

    def set_default(self, task_type: str, estimate: ResourceEstimate):
        self._defaults[task_type] = estimate

    def record(self, metrics: TaskMetrics):
        with self._lock:
            if metrics.task_type not in self._history:
                self._history[metrics.task_type] = []

            self._history[metrics.task_type].append(metrics)

            if len(self._history[metrics.task_type]) > self.max_history:
                self._history[metrics.task_type] = self._history[metrics.task_type][
                    -self.max_history :
                ]

    def estimate(self, task_type: str, input_size: int = 0) -> ResourceEstimate:
        with self._lock:
            historical_data = self._history.get(task_type, [])

            if not historical_data:
                default = self._defaults.get(task_type)
                if default:
                    return default
                return ResourceEstimate()

            return self.strategy.estimate(task_type, input_size, historical_data)

    def estimate_batch(self, tasks: list[tuple[str, int]]) -> ResourceEstimate:
        total = ResourceEstimate()

        for task_type, input_size in tasks:
            estimate = self.estimate(task_type, input_size)
            total = total + estimate

        return total

    def get_statistics(self, task_type: str) -> dict[str, Any]:
        with self._lock:
            data = self._history.get(task_type, [])

            if not data:
                return {"count": 0}

            success_data = [m for m in data if m.success]

            return {
                "total_count": len(data),
                "success_count": len(success_data),
                "avg_duration": (
                    statistics.mean(m.actual_duration for m in success_data) if success_data else 0
                ),
                "avg_memory": (
                    statistics.mean(m.actual_memory for m in success_data) if success_data else 0
                ),
                "avg_cpu": (
                    statistics.mean(m.actual_cpu for m in success_data) if success_data else 0
                ),
                "success_rate": len(success_data) / len(data) if data else 0,
            }

    def clear_history(self, task_type: str | None = None):
        with self._lock:
            if task_type:
                self._history.pop(task_type, None)
            else:
                self._history.clear()


class ResourceProfiler:
    def __init__(self, estimator: ResourceEstimator):
        self.estimator = estimator
        self._active_tasks: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def start_task(self, task_id: str, task_type: str, input_size: int = 0):
        with self._lock:
            self._active_tasks[task_id] = {
                "task_type": task_type,
                "input_size": input_size,
                "start_time": time.time(),
                "start_cpu": 0,
                "start_memory": 0,
            }

    def end_task(
        self, task_id: str, success: bool = True, node_id: str | None = None
    ) -> TaskMetrics | None:
        with self._lock:
            task_info = self._active_tasks.pop(task_id, None)

            if not task_info:
                return None

            duration = time.time() - task_info["start_time"]

            metrics = TaskMetrics(
                task_type=task_info["task_type"],
                input_size=task_info["input_size"],
                actual_cpu=0,
                actual_memory=0,
                actual_disk=0,
                actual_network=0,
                actual_duration=duration,
                success=success,
                node_id=node_id,
            )

            self.estimator.record(metrics)
            return metrics

    def get_active_count(self) -> int:
        with self._lock:
            return len(self._active_tasks)


__all__ = [
    "ResourceType",
    "ResourceEstimate",
    "TaskMetrics",
    "EstimationStrategy",
    "LinearRegressionEstimator",
    "PercentileEstimator",
    "WeightedAverageEstimator",
    "ResourceEstimator",
    "ResourceProfiler",
]

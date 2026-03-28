"""
Monitoring and Metrics Collection Module.

This module provides Prometheus-compatible metrics collection
and monitoring capabilities.

Architecture Reference:
- Prometheus: https://prometheus.io/docs/concepts/data_model/
- OpenMetrics: https://github.com/OpenObservability/OpenMetrics
"""
import asyncio
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class MetricType(str, Enum):
    """Metric type enumeration."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricSample:
    """A single metric sample."""
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class Metric:
    """Base class for metrics."""

    def __init__(
        self,
        name: str,
        description: str = "",
        labels: Optional[dict[str, str]] = None
    ):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self._lock = threading.Lock()

    def _label_key(self, labels: dict[str, str]) -> str:
        """Generate a key from labels."""
        if not labels:
            return ""
        return ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))


class Counter(Metric):
    """
    A counter that only increases.

    Usage:
        counter = Counter("tasks_total", "Total number of tasks")
        counter.inc()
        counter.inc(5)
    """

    def __init__(self, name: str, description: str = "", labels: Optional[dict[str, str]] = None):
        super().__init__(name, description, labels)
        self._value = 0.0

    def inc(self, amount: float = 1.0):
        """Increment counter by amount."""
        if amount < 0:
            raise ValueError("Counter can only increase")

        with self._lock:
            self._value += amount

    def get(self) -> float:
        """Get current value."""
        with self._lock:
            return self._value

    def collect(self) -> list[MetricSample]:
        """Collect metric samples."""
        return [MetricSample(
            name=self.name,
            value=self._value,
            labels=self.labels
        )]


class Gauge(Metric):
    """
    A gauge that can increase or decrease.

    Usage:
        gauge = Gauge("active_nodes", "Number of active nodes")
        gauge.set(10)
        gauge.inc()
        gauge.dec()
    """

    def __init__(self, name: str, description: str = "", labels: Optional[dict[str, str]] = None):
        super().__init__(name, description, labels)
        self._value = 0.0

    def set(self, value: float):
        """Set gauge to value."""
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1.0):
        """Increment gauge by amount."""
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0):
        """Decrement gauge by amount."""
        with self._lock:
            self._value -= amount

    def get(self) -> float:
        """Get current value."""
        with self._lock:
            return self._value

    def collect(self) -> list[MetricSample]:
        """Collect metric samples."""
        return [MetricSample(
            name=self.name,
            value=self._value,
            labels=self.labels
        )]


class Histogram(Metric):
    """
    A histogram that observes values and counts them in buckets.

    Usage:
        histogram = Histogram("task_duration_seconds", "Task duration")
        histogram.observe(0.5)
        histogram.observe(1.2)
    """

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(
        self,
        name: str,
        description: str = "",
        labels: Optional[dict[str, str]] = None,
        buckets: tuple = DEFAULT_BUCKETS
    ):
        super().__init__(name, description, labels)
        self.buckets = sorted(buckets)
        self._counts = [0.0] * (len(buckets) + 1)
        self._sum = 0.0
        self._count = 0.0

    def observe(self, value: float):
        """Observe a value."""
        with self._lock:
            self._sum += value
            self._count += 1

            for i, bucket in enumerate(self.buckets):
                if value <= bucket:
                    self._counts[i] += 1
                    break
            else:
                self._counts[-1] += 1

    def collect(self) -> list[MetricSample]:
        """Collect metric samples."""
        samples = []

        cumulative = 0.0
        for i, bucket in enumerate(self.buckets):
            cumulative += self._counts[i]
            samples.append(MetricSample(
                name=f"{self.name}_bucket",
                value=cumulative,
                labels={**self.labels, "le": str(bucket)}
            ))

        cumulative += self._counts[-1]
        samples.append(MetricSample(
            name=f"{self.name}_bucket",
            value=cumulative,
            labels={**self.labels, "le": "+Inf"}
        ))

        samples.append(MetricSample(
            name=f"{self.name}_sum",
            value=self._sum,
            labels=self.labels
        ))

        samples.append(MetricSample(
            name=f"{self.name}_count",
            value=self._count,
            labels=self.labels
        ))

        return samples


class MetricsRegistry:
    """
    Central registry for all metrics.

    Usage:
        registry = MetricsRegistry()

        # Register metrics
        registry.register(Counter("tasks_total", "Total tasks"))
        registry.register(Gauge("active_nodes", "Active nodes"))

        # Export in Prometheus format
        output = registry.export_prometheus()
    """

    def __init__(self, namespace: str = "idle_accelerator"):
        self.namespace = namespace
        self._metrics: dict[str, Metric] = {}
        self._lock = threading.Lock()

    def register(self, metric: Metric) -> Metric:
        """Register a metric."""
        with self._lock:
            if metric.name in self._metrics:
                return self._metrics[metric.name]
            self._metrics[metric.name] = metric
            return metric

    def unregister(self, name: str):
        """Unregister a metric."""
        with self._lock:
            self._metrics.pop(name, None)

    def counter(self, name: str, description: str = "") -> Counter:
        """Get or create a counter."""
        full_name = f"{self.namespace}_{name}"
        return self.register(Counter(full_name, description))

    def gauge(self, name: str, description: str = "") -> Gauge:
        """Get or create a gauge."""
        full_name = f"{self.namespace}_{name}"
        return self.register(Gauge(full_name, description))

    def histogram(
        self,
        name: str,
        description: str = "",
        buckets: tuple = Histogram.DEFAULT_BUCKETS
    ) -> Histogram:
        """Get or create a histogram."""
        full_name = f"{self.namespace}_{name}"
        return self.register(Histogram(full_name, description, buckets=buckets))

    def collect_all(self) -> list[MetricSample]:
        """Collect all metric samples."""
        samples = []
        with self._lock:
            for metric in self._metrics.values():
                samples.extend(metric.collect())
        return samples

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []

        samples = self.collect_all()

        current_metric = None
        for sample in samples:
            base_name = sample.name.split("_bucket")[0].split("_sum")[0].split("_count")[0]

            if base_name != current_metric:
                for name, metric in self._metrics.items():
                    if name == base_name:
                        lines.append(f"# HELP {base_name} {metric.description}")
                        lines.append(f"# TYPE {base_name} {self._get_type(metric)}")
                        break
                current_metric = base_name

            label_str = ""
            if sample.labels:
                label_str = "{" + ", ".join(f'{k}="{v}"' for k, v in sample.labels.items()) + "}"

            lines.append(f"{sample.name}{label_str} {sample.value}")

        return "\n".join(lines)

    def _get_type(self, metric: Metric) -> str:
        """Get metric type string."""
        if isinstance(metric, Counter):
            return "counter"
        elif isinstance(metric, Gauge):
            return "gauge"
        elif isinstance(metric, Histogram):
            return "histogram"
        return "unknown"


class SystemMonitor:
    """
    System monitoring and metrics collection.

    Usage:
        monitor = SystemMonitor()
        monitor.start()

        # Get metrics
        stats = monitor.get_stats()

        # Export for Prometheus
        prometheus_output = monitor.export_prometheus()
    """

    def __init__(self, registry: Optional[MetricsRegistry] = None):
        self.registry = registry or MetricsRegistry()

        self.tasks_total = self.registry.counter("tasks_total", "Total tasks submitted")
        self.tasks_completed = self.registry.counter("tasks_completed", "Total tasks completed")
        self.tasks_failed = self.registry.counter("tasks_failed", "Total tasks failed")
        self.tasks_pending = self.registry.gauge("tasks_pending", "Current pending tasks")
        self.tasks_running = self.registry.gauge("tasks_running", "Current running tasks")

        self.nodes_total = self.registry.gauge("nodes_total", "Total registered nodes")
        self.nodes_available = self.registry.gauge("nodes_available", "Available nodes")
        self.nodes_offline = self.registry.gauge("nodes_offline", "Offline nodes")

        self.task_duration = self.registry.histogram(
            "task_duration_seconds",
            "Task execution duration"
        )

        self.scheduler_latency = self.registry.histogram(
            "scheduler_latency_seconds",
            "Scheduler decision latency"
        )

        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start monitoring."""
        self._running = True

    async def stop(self):
        """Stop monitoring."""
        self._running = False

    def record_task_submitted(self):
        """Record a task submission."""
        self.tasks_total.inc()

    def record_task_completed(self, duration: float, success: bool = True):
        """Record a task completion."""
        if success:
            self.tasks_completed.inc()
        else:
            self.tasks_failed.inc()

        self.task_duration.observe(duration)

    def update_task_counts(self, pending: int, running: int):
        """Update task count gauges."""
        self.tasks_pending.set(pending)
        self.tasks_running.set(running)

    def update_node_counts(self, total: int, available: int, offline: int):
        """Update node count gauges."""
        self.nodes_total.set(total)
        self.nodes_available.set(available)
        self.nodes_offline.set(offline)

    def record_scheduler_latency(self, latency: float):
        """Record scheduler decision latency."""
        self.scheduler_latency.observe(latency)

    def get_stats(self) -> dict[str, Any]:
        """Get current statistics."""
        return {
            "tasks": {
                "total": self.tasks_total.get(),
                "completed": self.tasks_completed.get(),
                "failed": self.tasks_failed.get(),
                "pending": self.tasks_pending.get(),
                "running": self.tasks_running.get(),
            },
            "nodes": {
                "total": self.nodes_total.get(),
                "available": self.nodes_available.get(),
                "offline": self.nodes_offline.get(),
            }
        }

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        return self.registry.export_prometheus()


def setup_metrics_endpoint(app, monitor: SystemMonitor):
    """
    Setup Prometheus metrics endpoint for FastAPI.

    Usage:
        from fastapi import FastAPI
        from monitoring import SystemMonitor, setup_metrics_endpoint

        app = FastAPI()
        monitor = SystemMonitor()
        setup_metrics_endpoint(app, monitor)
    """
    from fastapi import Response

    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        prometheus_output = monitor.export_prometheus()
        return Response(
            content=prometheus_output,
            media_type="text/plain; version=0.0.4"
        )

    @app.get("/stats")
    async def stats():
        """JSON stats endpoint."""
        return monitor.get_stats()

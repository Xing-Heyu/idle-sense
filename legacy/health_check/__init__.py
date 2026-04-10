"""Health Check System - Comprehensive health monitoring for nodes and services."""

from __future__ import annotations

import contextlib
import socket
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(str, Enum):
    SELF = "self"
    DEPENDENCY = "dependency"
    RESOURCE = "resource"
    NETWORK = "network"
    STORAGE = "storage"
    CUSTOM = "custom"


@dataclass
class HealthCheckResult:
    check_name: str
    check_type: CheckType
    status: HealthStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    duration_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_name": self.check_name,
            "check_type": self.check_type.value,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class HealthReport:
    component_id: str
    component_type: str
    status: HealthStatus
    checks: list[HealthCheckResult] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    uptime_seconds: float = 0

    @property
    def healthy_count(self) -> int:
        return sum(1 for c in self.checks if c.status == HealthStatus.HEALTHY)

    @property
    def unhealthy_count(self) -> int:
        return sum(1 for c in self.checks if c.status == HealthStatus.UNHEALTHY)

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_type": self.component_type,
            "status": self.status.value,
            "checks": [c.to_dict() for c in self.checks],
            "timestamp": self.timestamp,
            "uptime_seconds": self.uptime_seconds,
            "summary": {
                "total": len(self.checks),
                "healthy": self.healthy_count,
                "unhealthy": self.unhealthy_count,
            },
        }


class HealthCheck(ABC):
    def __init__(self, name: str, check_type: CheckType = CheckType.CUSTOM):
        self.name = name
        self.check_type = check_type
        self.timeout_seconds = 5.0
        self.critical = True

    @abstractmethod
    def execute(self) -> HealthCheckResult:
        pass

    def run(self) -> HealthCheckResult:
        start_time = time.time()
        try:
            result = self.execute()
        except Exception as e:
            result = HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )

        result.duration_ms = int((time.time() - start_time) * 1000)
        return result


class CPUHealthCheck(HealthCheck):
    def __init__(self, threshold_percent: float = 90.0):
        super().__init__("cpu", CheckType.RESOURCE)
        self.threshold_percent = threshold_percent

    def execute(self) -> HealthCheckResult:
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=1)

            if cpu_percent >= self.threshold_percent:
                return HealthCheckResult(
                    check_name=self.name,
                    check_type=self.check_type,
                    status=HealthStatus.UNHEALTHY,
                    message=f"CPU usage {cpu_percent}% exceeds threshold {self.threshold_percent}%",
                    details={"cpu_percent": cpu_percent, "threshold": self.threshold_percent},
                )
            elif cpu_percent >= self.threshold_percent * 0.8:
                return HealthCheckResult(
                    check_name=self.name,
                    check_type=self.check_type,
                    status=HealthStatus.DEGRADED,
                    message=f"CPU usage {cpu_percent}% is high",
                    details={"cpu_percent": cpu_percent, "threshold": self.threshold_percent},
                )

            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.HEALTHY,
                message=f"CPU usage is normal at {cpu_percent}%",
                details={"cpu_percent": cpu_percent},
            )
        except ImportError:
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNKNOWN,
                message="psutil not available",
            )


class MemoryHealthCheck(HealthCheck):
    def __init__(self, threshold_percent: float = 90.0):
        super().__init__("memory", CheckType.RESOURCE)
        self.threshold_percent = threshold_percent

    def execute(self) -> HealthCheckResult:
        try:
            import psutil

            memory = psutil.virtual_memory()

            if memory.percent >= self.threshold_percent:
                return HealthCheckResult(
                    check_name=self.name,
                    check_type=self.check_type,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Memory usage {memory.percent}% exceeds threshold",
                    details={
                        "percent": memory.percent,
                        "available_mb": memory.available / 1024 / 1024,
                        "total_mb": memory.total / 1024 / 1024,
                    },
                )
            elif memory.percent >= self.threshold_percent * 0.8:
                return HealthCheckResult(
                    check_name=self.name,
                    check_type=self.check_type,
                    status=HealthStatus.DEGRADED,
                    message=f"Memory usage {memory.percent}% is high",
                    details={"percent": memory.percent},
                )

            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.HEALTHY,
                message=f"Memory usage is normal at {memory.percent}%",
                details={"percent": memory.percent},
            )
        except ImportError:
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNKNOWN,
                message="psutil not available",
            )


class DiskHealthCheck(HealthCheck):
    def __init__(self, path: str = "/", threshold_percent: float = 90.0):
        super().__init__("disk", CheckType.STORAGE)
        self.path = path
        self.threshold_percent = threshold_percent

    def execute(self) -> HealthCheckResult:
        try:
            import psutil

            disk = psutil.disk_usage(self.path)

            if disk.percent >= self.threshold_percent:
                return HealthCheckResult(
                    check_name=self.name,
                    check_type=self.check_type,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Disk usage {disk.percent}% exceeds threshold",
                    details={
                        "path": self.path,
                        "percent": disk.percent,
                        "free_gb": disk.free / 1024 / 1024 / 1024,
                    },
                )

            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.HEALTHY,
                message=f"Disk usage is normal at {disk.percent}%",
                details={"path": self.path, "percent": disk.percent},
            )
        except ImportError:
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNKNOWN,
                message="psutil not available",
            )
        except Exception as e:
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )


class NetworkHealthCheck(HealthCheck):
    def __init__(self, host: str = "8.8.8.8", port: int = 53, timeout: float = 5.0):
        super().__init__("network", CheckType.NETWORK)
        self.host = host
        self.port = port
        self.timeout = timeout

    def execute(self) -> HealthCheckResult:
        try:
            start = time.time()
            socket.setdefaulttimeout(self.timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((self.host, self.port))
            latency = (time.time() - start) * 1000

            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.HEALTHY,
                message=f"Network connectivity OK, latency: {latency:.2f}ms",
                details={"host": self.host, "latency_ms": latency},
            )
        except socket.timeout:
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNHEALTHY,
                message="Network connection timed out",
                details={"host": self.host},
            )
        except Exception as e:
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )


class HTTPHealthCheck(HealthCheck):
    def __init__(self, name: str, url: str, expected_status: int = 200, timeout: float = 5.0):
        super().__init__(name, CheckType.DEPENDENCY)
        self.url = url
        self.expected_status = expected_status
        self.timeout = timeout

    def execute(self) -> HealthCheckResult:
        try:
            import urllib.error
            import urllib.request

            start = time.time()
            req = urllib.request.Request(self.url, method="GET")

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                status = response.status
                latency = (time.time() - start) * 1000

                if status == self.expected_status:
                    return HealthCheckResult(
                        check_name=self.name,
                        check_type=self.check_type,
                        status=HealthStatus.HEALTHY,
                        message=f"HTTP check passed, status: {status}",
                        details={"url": self.url, "status": status, "latency_ms": latency},
                    )
                else:
                    return HealthCheckResult(
                        check_name=self.name,
                        check_type=self.check_type,
                        status=HealthStatus.UNHEALTHY,
                        message=f"Unexpected status code: {status}",
                        details={
                            "url": self.url,
                            "status": status,
                            "expected": self.expected_status,
                        },
                    )
        except urllib.error.HTTPError as e:
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNHEALTHY,
                message=f"HTTP error: {e.code}",
                details={"url": self.url, "status": e.code},
            )
        except Exception as e:
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )


class TCPHealthCheck(HealthCheck):
    def __init__(self, name: str, host: str, port: int, timeout: float = 5.0):
        super().__init__(name, CheckType.NETWORK)
        self.host = host
        self.port = port
        self.timeout = timeout

    def execute(self) -> HealthCheckResult:
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((self.host, self.port))
            latency = (time.time() - start) * 1000
            sock.close()

            if result == 0:
                return HealthCheckResult(
                    check_name=self.name,
                    check_type=self.check_type,
                    status=HealthStatus.HEALTHY,
                    message=f"TCP port {self.port} is open",
                    details={"host": self.host, "port": self.port, "latency_ms": latency},
                )
            else:
                return HealthCheckResult(
                    check_name=self.name,
                    check_type=self.check_type,
                    status=HealthStatus.UNHEALTHY,
                    message=f"TCP port {self.port} is closed",
                    details={"host": self.host, "port": self.port},
                )
        except Exception as e:
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )


class CustomHealthCheck(HealthCheck):
    def __init__(self, name: str, check_func: Callable[[], tuple[bool, str, dict[str, Any]]]):
        super().__init__(name, CheckType.CUSTOM)
        self.check_func = check_func

    def execute(self) -> HealthCheckResult:
        try:
            is_healthy, message, details = self.check_func()
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
                message=message,
                details=details,
            )
        except Exception as e:
            return HealthCheckResult(
                check_name=self.name,
                check_type=self.check_type,
                status=HealthStatus.UNHEALTHY,
                error=str(e),
            )


class HealthChecker:
    def __init__(self, component_id: str, component_type: str = "node"):
        self.component_id = component_id
        self.component_type = component_type
        self.checks: dict[str, HealthCheck] = {}
        self._start_time = time.time()
        self._lock = threading.RLock()

    def register_check(self, check: HealthCheck):
        with self._lock:
            self.checks[check.name] = check

    def remove_check(self, name: str) -> bool:
        with self._lock:
            if name in self.checks:
                del self.checks[name]
                return True
            return False

    def run_check(self, name: str) -> HealthCheckResult | None:
        with self._lock:
            check = self.checks.get(name)
            if check:
                return check.run()
        return None

    def run_all(self) -> HealthReport:
        with self._lock:
            checks = list(self.checks.values())

        results = []
        for check in checks:
            results.append(check.run())

        overall_status = HealthStatus.HEALTHY
        for result in results:
            if result.status == HealthStatus.UNHEALTHY and result.check_name in self.checks:
                check = self.checks[result.check_name]
                if getattr(check, "critical", True):
                    overall_status = HealthStatus.UNHEALTHY
                    break
            elif result.status == HealthStatus.DEGRADED:
                if overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED

        return HealthReport(
            component_id=self.component_id,
            component_type=self.component_type,
            status=overall_status,
            checks=results,
            uptime_seconds=time.time() - self._start_time,
        )

    def is_healthy(self) -> bool:
        report = self.run_all()
        return report.status == HealthStatus.HEALTHY

    def get_status(self) -> HealthStatus:
        report = self.run_all()
        return report.status


class HealthMonitor:
    def __init__(self, check_interval: float = 30.0):
        self.check_interval = check_interval
        self._checkers: dict[str, HealthChecker] = {}
        self._callbacks: list[Callable[[HealthReport], None]] = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()

    def register_checker(self, checker: HealthChecker):
        with self._lock:
            self._checkers[checker.component_id] = checker

    def unregister_checker(self, component_id: str):
        with self._lock:
            self._checkers.pop(component_id, None)

    def add_callback(self, callback: Callable[[HealthReport], None]):
        with self._lock:
            self._callbacks.append(callback)

    def check_all(self) -> dict[str, HealthReport]:
        with self._lock:
            checkers = dict(self._checkers)

        reports = {}
        for component_id, checker in checkers.items():
            reports[component_id] = checker.run_all()

        return reports

    def start(self):
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _monitor_loop(self):
        while self._running:
            try:
                reports = self.check_all()

                with self._lock:
                    callbacks = list(self._callbacks)

                for report in reports.values():
                    for callback in callbacks:
                        with contextlib.suppress(Exception):
                            callback(report)

            except Exception:
                pass

            time.sleep(self.check_interval)


__all__ = [
    "HealthStatus",
    "CheckType",
    "HealthCheckResult",
    "HealthReport",
    "HealthCheck",
    "CPUHealthCheck",
    "MemoryHealthCheck",
    "DiskHealthCheck",
    "NetworkHealthCheck",
    "HTTPHealthCheck",
    "TCPHealthCheck",
    "CustomHealthCheck",
    "HealthChecker",
    "HealthMonitor",
]

"""
Health Check and Diagnostics Module.

This module provides comprehensive health checking and diagnostic
capabilities for the idle-accelerator system.
"""
import json
import os
import platform
import socket
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None


class HealthStatus(str, Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


@dataclass
class SystemDiagnostics:
    """System diagnostics information."""
    hostname: str
    platform: str
    python_version: str
    cpu_count: int
    memory_total_gb: float
    disk_total_gb: float
    network_interfaces: list[str]
    environment: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hostname": self.hostname,
            "platform": self.platform,
            "python_version": self.python_version,
            "cpu_count": self.cpu_count,
            "memory_total_gb": self.memory_total_gb,
            "disk_total_gb": self.disk_total_gb,
            "network_interfaces": self.network_interfaces,
            "environment": self.environment,
        }


class HealthChecker:
    """
    Comprehensive health checker.

    Usage:
        checker = HealthChecker()

        # Register custom checks
        checker.register("database", check_database)
        checker.register("redis", check_redis)

        # Run all checks
        results = checker.run_all()

        # Get overall status
        status = checker.get_overall_status(results)
    """

    def __init__(self):
        self._checks: dict[str, Callable] = {}
        self._register_default_checks()

    def _register_default_checks(self):
        """Register default health checks."""
        self.register("system", self._check_system)
        self.register("memory", self._check_memory)
        self.register("disk", self._check_disk)
        self.register("network", self._check_network)

    def register(self, name: str, check_func: Callable):
        """Register a health check."""
        self._checks[name] = check_func

    def unregister(self, name: str):
        """Unregister a health check."""
        self._checks.pop(name, None)

    def run_check(self, name: str) -> HealthCheckResult:
        """Run a specific health check."""
        check_func = self._checks.get(name)

        if not check_func:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"Health check '{name}' not found"
            )

        start_time = time.time()

        try:
            result = check_func()

            if isinstance(result, HealthCheckResult):
                result.duration_ms = (time.time() - start_time) * 1000
                return result

            if isinstance(result, dict):
                return HealthCheckResult(
                    name=name,
                    status=HealthStatus(result.get("status", "unknown")),
                    message=result.get("message", ""),
                    details=result.get("details", {}),
                    duration_ms=(time.time() - start_time) * 1000
                )

            return HealthCheckResult(
                name=name,
                status=HealthStatus.HEALTHY,
                message="Check passed",
                duration_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000
            )

    def run_all(self) -> list[HealthCheckResult]:
        """Run all registered health checks."""
        results = []

        for name in self._checks:
            results.append(self.run_check(name))

        return results

    def get_overall_status(self, results: list[HealthCheckResult]) -> HealthStatus:
        """Get overall health status from results."""
        if not results:
            return HealthStatus.UNKNOWN

        statuses = [r.status for r in results]

        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY

        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED

        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY

        return HealthStatus.UNKNOWN

    def _check_system(self) -> HealthCheckResult:
        """Check system health."""
        try:
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)

            return HealthCheckResult(
                name="system",
                status=HealthStatus.HEALTHY,
                message="System is healthy",
                details={
                    "platform": platform.system(),
                    "platform_version": platform.version(),
                    "load_average": load_avg,
                    "uptime": time.time() - psutil.boot_time() if PSUTIL_AVAILABLE else "unknown"
                }
            )
        except Exception as e:
            return HealthCheckResult(
                name="system",
                status=HealthStatus.DEGRADED,
                message=f"System check warning: {str(e)}"
            )

    def _check_memory(self) -> HealthCheckResult:
        """Check memory health."""
        try:
            if self._has_psutil():
                import psutil
                memory = psutil.virtual_memory()

                if memory.percent > 90:
                    status = HealthStatus.UNHEALTHY
                    message = f"Memory usage critical: {memory.percent}%"
                elif memory.percent > 75:
                    status = HealthStatus.DEGRADED
                    message = f"Memory usage high: {memory.percent}%"
                else:
                    status = HealthStatus.HEALTHY
                    message = f"Memory usage normal: {memory.percent}%"

                return HealthCheckResult(
                    name="memory",
                    status=status,
                    message=message,
                    details={
                        "total_gb": round(memory.total / (1024**3), 2),
                        "available_gb": round(memory.available / (1024**3), 2),
                        "used_percent": memory.percent
                    }
                )

            return HealthCheckResult(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message="psutil not available"
            )
        except Exception as e:
            return HealthCheckResult(
                name="memory",
                status=HealthStatus.UNHEALTHY,
                message=f"Memory check failed: {str(e)}"
            )

    def _check_disk(self) -> HealthCheckResult:
        """Check disk health."""
        try:
            if self._has_psutil():
                import psutil
                disk = psutil.disk_usage('/')

                if disk.percent > 95:
                    status = HealthStatus.UNHEALTHY
                    message = f"Disk usage critical: {disk.percent}%"
                elif disk.percent > 85:
                    status = HealthStatus.DEGRADED
                    message = f"Disk usage high: {disk.percent}%"
                else:
                    status = HealthStatus.HEALTHY
                    message = f"Disk usage normal: {disk.percent}%"

                return HealthCheckResult(
                    name="disk",
                    status=status,
                    message=message,
                    details={
                        "total_gb": round(disk.total / (1024**3), 2),
                        "free_gb": round(disk.free / (1024**3), 2),
                        "used_percent": disk.percent
                    }
                )

            return HealthCheckResult(
                name="disk",
                status=HealthStatus.UNKNOWN,
                message="psutil not available"
            )
        except Exception as e:
            return HealthCheckResult(
                name="disk",
                status=HealthStatus.UNHEALTHY,
                message=f"Disk check failed: {str(e)}"
            )

    def _check_network(self) -> HealthCheckResult:
        """Check network health."""
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=5)

            return HealthCheckResult(
                name="network",
                status=HealthStatus.HEALTHY,
                message="Network connectivity OK",
                details={
                    "internet_reachable": True
                }
            )
        except Exception as e:
            return HealthCheckResult(
                name="network",
                status=HealthStatus.DEGRADED,
                message=f"Network connectivity issue: {str(e)}",
                details={
                    "internet_reachable": False
                }
            )

    def _has_psutil(self) -> bool:
        """Check if psutil is available."""
        return PSUTIL_AVAILABLE


class DiagnosticsCollector:
    """Collector for system diagnostics."""

    @staticmethod
    def collect() -> SystemDiagnostics:
        """Collect system diagnostics."""
        hostname = socket.gethostname()
        platform_info = f"{platform.system()} {platform.release()}"
        python_version = platform.python_version()
        cpu_count = os.cpu_count() or 1

        memory_total_gb = 0.0
        disk_total_gb = 0.0
        network_interfaces = []

        try:
            import psutil

            memory = psutil.virtual_memory()
            memory_total_gb = round(memory.total / (1024**3), 2)

            disk = psutil.disk_usage('/')
            disk_total_gb = round(disk.total / (1024**3), 2)

            network_interfaces = list(psutil.net_if_addrs().keys())
        except ImportError:
            pass

        env_vars = {
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
            "PATH": os.environ.get("PATH", "")[:100] + "...",
        }

        return SystemDiagnostics(
            hostname=hostname,
            platform=platform_info,
            python_version=python_version,
            cpu_count=cpu_count,
            memory_total_gb=memory_total_gb,
            disk_total_gb=disk_total_gb,
            network_interfaces=network_interfaces,
            environment=env_vars
        )


def create_health_endpoint(app, checker: Optional[HealthChecker] = None):
    """
    Create health check endpoints for FastAPI.

    Usage:
        from fastapi import FastAPI
        from diagnostics import create_health_endpoint

        app = FastAPI()
        create_health_endpoint(app)
    """
    from fastapi import Response

    checker = checker or HealthChecker()

    @app.get("/health")
    async def health():
        """Basic health check."""
        return {"status": "healthy", "timestamp": time.time()}

    @app.get("/health/live")
    async def liveness():
        """Kubernetes liveness probe."""
        return {"status": "alive"}

    @app.get("/health/ready")
    async def readiness():
        """Kubernetes readiness probe."""
        results = checker.run_all()
        overall = checker.get_overall_status(results)

        if overall in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]:
            return {"status": "ready", "overall": overall.value}

        return Response(
            content=json.dumps({"status": "not_ready", "overall": overall.value}),
            status_code=503,
            media_type="application/json"
        )

    @app.get("/health/detailed")
    async def detailed_health():
        """Detailed health check."""
        results = checker.run_all()
        overall = checker.get_overall_status(results)

        return {
            "overall_status": overall.value,
            "checks": [r.to_dict() for r in results],
            "timestamp": time.time()
        }

    @app.get("/diagnostics")
    async def diagnostics():
        """System diagnostics."""
        diag = DiagnosticsCollector.collect()
        return diag.to_dict()

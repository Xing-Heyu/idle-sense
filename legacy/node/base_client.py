"""
Base Node Client - Common functionality for all node clients.

This module provides the abstract base class and shared functionality
for node clients, reducing code duplication between platform-specific implementations.
"""
import hashlib
import logging
import platform
import socket
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class NodeState(str, Enum):
    """Node state enumeration."""
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


@dataclass
class NodeCapacity:
    """Node resource capacity."""
    cpu: float = 4.0
    memory: int = 8192
    disk: int = 50000
    gpu: bool = False
    gpu_memory: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpu": self.cpu,
            "memory": self.memory,
            "disk": self.disk,
            "gpu": self.gpu,
            "gpu_memory": self.gpu_memory,
        }


@dataclass
class NodeConfig:
    """Node client configuration."""
    scheduler_url: str = "http://localhost:8000"
    idle_threshold: int = 300
    cpu_threshold: float = 30.0
    memory_threshold: float = 70.0
    heartbeat_interval: int = 30
    check_interval: int = 30
    max_task_time: int = 300
    max_memory_mb: int = 1024
    silent_mode: bool = True
    auto_start: bool = True


class BaseNodeClient(ABC):
    """
    Abstract base class for node clients.

    Provides common functionality:
    - Node registration
    - Heartbeat management
    - Task execution loop
    - Resource monitoring

    Platform-specific implementations should inherit from this class
    and implement the abstract methods.
    """

    def __init__(self, config: Optional[NodeConfig] = None):
        self.config = config or NodeConfig()
        self.node_id = self._generate_node_id()
        self.state = NodeState.INITIALIZING
        self.capacity = self._detect_capacity()
        self.running = False
        self.is_registered = False
        self.current_task: Optional[dict[str, Any]] = None
        self._last_heartbeat = 0.0
        self._task_count = 0
        self._error_count = 0

    def _generate_node_id(self) -> str:
        """Generate a unique node ID."""
        hostname = socket.gethostname()
        unique = f"{hostname}-{platform.system()}-{uuid.uuid4().hex[:8]}"
        return hashlib.md5(unique.encode()).hexdigest()[:16]

    @abstractmethod
    def _detect_capacity(self) -> NodeCapacity:
        """Detect node resource capacity."""
        pass

    @abstractmethod
    def _check_idle(self) -> tuple[bool, dict[str, Any]]:
        """
        Check if the system is idle.

        Returns:
            Tuple of (is_idle, status_dict)
        """
        pass

    @abstractmethod
    def _execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a task.

        Args:
            task: Task information dictionary

        Returns:
            Execution result dictionary
        """
        pass

    def _get_device_type(self) -> str:
        """Detect device type based on capacity."""
        cpu = self.capacity.cpu
        memory = self.capacity.memory

        if cpu >= 8 and memory >= 16384:
            return "gaming_laptop"
        elif cpu <= 4 and memory <= 8192:
            return "ultrabook"
        else:
            return "desktop"

    def _log(self, message: str, level: str = "info") -> None:
        """Log a message (respects silent mode)."""
        if not self.config.silent_mode:
            print(f"[{level.upper()}] {message}")

        log_func = getattr(logger, level, logger.info)
        log_func(message)

    def register(self) -> bool:
        """Register this node with the scheduler."""
        try:
            import requests

            response = requests.post(
                f"{self.config.scheduler_url}/api/nodes/register",
                json={
                    "node_id": self.node_id,
                    "capacity": self.capacity.to_dict(),
                    "tags": {
                        "device_type": self._get_device_type(),
                        "platform": platform.system(),
                        "gpu": self.capacity.gpu,
                    }
                },
                timeout=10
            )

            if response.status_code == 200:
                self.is_registered = True
                self.state = NodeState.IDLE
                self._log(f"Node registered: {self.node_id}")
                return True
            else:
                self._log(f"Registration failed: {response.status_code}", "error")
                return False

        except Exception as e:
            self._log(f"Registration error: {e}", "error")
            return False

    def send_heartbeat(self) -> bool:
        """Send heartbeat to the scheduler."""
        if not self.is_registered:
            return False

        try:
            import requests

            is_idle, status = self._check_idle()

            response = requests.post(
                f"{self.config.scheduler_url}/api/nodes/{self.node_id}/heartbeat",
                json={
                    "node_id": self.node_id,
                    "current_load": {
                        "cpu_usage": status.get("cpu_percent", 0),
                        "memory_usage": status.get("memory_percent", 0),
                    },
                    "is_idle": is_idle,
                    "available_resources": {
                        "cpu": self.capacity.cpu * (1 - status.get("cpu_percent", 0) / 100),
                        "memory": self.capacity.memory * (1 - status.get("memory_percent", 0) / 100),
                    },
                    "cpu_usage": status.get("cpu_percent", 0),
                    "memory_usage": status.get("memory_percent", 0),
                    "is_available": self.state != NodeState.ERROR,
                },
                timeout=10
            )

            self._last_heartbeat = time.time()

            if response.status_code == 200:
                return True
            else:
                self._log(f"Heartbeat failed: {response.status_code}", "warning")
                return False

        except Exception as e:
            self._log(f"Heartbeat error: {e}", "warning")
            return False

    def get_task(self) -> Optional[dict[str, Any]]:
        """Request a task from the scheduler."""
        try:
            import requests

            response = requests.get(
                f"{self.config.scheduler_url}/get_task",
                params={"node_id": self.node_id},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("task_id"):
                    return data

            return None

        except Exception as e:
            self._log(f"Get task error: {e}", "warning")
            return None

    def submit_result(
        self,
        task_id: int,
        result: Any,
        success: bool = True,
        error: Optional[str] = None
    ) -> bool:
        """Submit task result to the scheduler."""
        try:
            import requests

            response = requests.post(
                f"{self.config.scheduler_url}/submit_result",
                json={
                    "task_id": task_id,
                    "result": str(result) if result else None,
                    "node_id": self.node_id,
                    "success": success,
                    "error": error,
                },
                timeout=10
            )

            return response.status_code == 200

        except Exception as e:
            self._log(f"Submit result error: {e}", "error")
            return False

    def run_task_loop(self) -> None:
        """Main task execution loop."""
        while self.running:
            try:
                is_idle, _ = self._check_idle()

                if is_idle and self.state == NodeState.IDLE:
                    task = self.get_task()

                    if task:
                        self.state = NodeState.BUSY
                        self.current_task = task
                        self._task_count += 1

                        self._log(f"Executing task {task['task_id']}")

                        try:
                            result = self._execute_task(task)
                            self.submit_result(
                                task_id=task["task_id"],
                                result=result.get("result"),
                                success=result.get("success", True),
                                error=result.get("error")
                            )
                        except Exception as e:
                            self._error_count += 1
                            self.submit_result(
                                task_id=task["task_id"],
                                result=None,
                                success=False,
                                error=str(e)
                            )

                        self.current_task = None
                        self.state = NodeState.IDLE

                if time.time() - self._last_heartbeat > self.config.heartbeat_interval:
                    self.send_heartbeat()

                time.sleep(self.config.check_interval)

            except Exception as e:
                self._log(f"Task loop error: {e}", "error")
                self.state = NodeState.ERROR
                time.sleep(5)
                self.state = NodeState.IDLE

    def start(self) -> None:
        """Start the node client."""
        self._log(f"Starting node client: {self.node_id}")
        self._log(f"Scheduler: {self.config.scheduler_url}")
        self._log(f"Capacity: CPU={self.capacity.cpu}, Memory={self.capacity.memory}MB")

        if not self.register():
            self._log("Failed to register, retrying...", "warning")
            time.sleep(5)
            if not self.register():
                self._log("Registration failed, exiting", "error")
                return

        self.running = True
        self.state = NodeState.IDLE

        try:
            self.run_task_loop()
        except KeyboardInterrupt:
            self._log("Shutting down...")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the node client."""
        self.running = False
        self.state = NodeState.OFFLINE
        self._log("Node client stopped")

    def get_stats(self) -> dict[str, Any]:
        """Get node statistics."""
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "capacity": self.capacity.to_dict(),
            "is_registered": self.is_registered,
            "task_count": self._task_count,
            "error_count": self._error_count,
            "last_heartbeat": self._last_heartbeat,
            "current_task": self.current_task.get("task_id") if self.current_task else None,
        }

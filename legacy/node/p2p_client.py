"""
P2P Client - Distributed Computing Node with Peer-to-Peer Networking.

This client extends P2PNode to provide:
- Distributed task execution
- Peer discovery via Kademlia DHT
- Task/result broadcasting via Gossip Protocol
- NAT traversal for peer connectivity

Usage:
    # Start a bootstrap node (first node in network)
    python -m legacy.node.p2p_client --bootstrap --port 8765

    # Start a worker node connecting to bootstrap
    python -m legacy.node.p2p_client --bootstrap-node 192.168.1.1:8765

    # Submit a task to the network
    python -m legacy.node.p2p_client --submit "print('Hello P2P!')"
"""

import argparse
import asyncio
import hashlib
import json
import os
import platform
import socket
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from legacy.p2p_network import (
    GossipProtocol,
    KademliaDHT,
    Message,
    MessageType,
    NATTraversal,
    P2PNode,
    PeerInfo,
    PeerState,
)

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


@dataclass
class Task:
    task_id: str
    code: str
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    assigned_node: Optional[str] = None
    result: Optional[str] = None
    completed_at: Optional[float] = None
    required_resources: dict = field(default_factory=lambda: {"cpu": 1.0, "memory": 512})
    priority: int = 0
    timeout: int = 300


@dataclass
class TaskResult:
    task_id: str
    node_id: str
    result: str
    execution_time: float
    success: bool = True
    error: Optional[str] = None


class P2PClient(P2PNode):
    """P2P Computing Client with distributed task execution.

    Extends P2PNode with:
    - Idle detection and resource monitoring
    - Task execution capabilities
    - Task queue management
    - Result broadcasting
    """

    CHECK_INTERVAL = 30
    HEARTBEAT_INTERVAL = 20
    TASK_TIMEOUT = 300
    MAX_PENDING_TASKS = 10

    def __init__(
        self,
        node_id: str = None,
        port: int = None,
        capabilities: dict[str, Any] = None,
        bootstrap_nodes: list[tuple[str, int]] = None,
        is_bootstrap: bool = False,
        scheduler_mode: bool = False,
    ):
        self._is_bootstrap = is_bootstrap
        self._scheduler_mode = scheduler_mode

        capabilities = capabilities or {}
        capabilities.update(self._detect_capabilities())

        super().__init__(
            node_id=node_id,
            port=port,
            capabilities=capabilities,
            bootstrap_nodes=bootstrap_nodes,
        )

        self.device_type = self._detect_device_type()
        self.capacity = self._get_capacity_by_device_type()

        self._pending_tasks: dict[str, Task] = {}
        self._completed_tasks: dict[str, TaskResult] = {}
        self._task_queue: list[Task] = []
        self._running_task: Optional[Task] = None
        self._task_count = 0
        self._error_count = 0
        self._total_compute_time = 0.0
        self._start_time = time.time()

        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

        self._register_task_handlers()

    def _detect_capabilities(self) -> dict[str, Any]:
        capabilities = {
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "hostname": socket.gethostname(),
        }

        if PSUTIL_AVAILABLE:
            try:
                capabilities.update(
                    {
                        "cpu_cores": psutil.cpu_count(logical=True),
                        "memory_total_gb": psutil.virtual_memory().total / (1024**3),
                        "cpu_freq_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else 0,
                    }
                )
            except Exception:
                pass

        return capabilities

    def _detect_device_type(self) -> str:
        try:
            if PSUTIL_AVAILABLE:
                cpu_cores = psutil.cpu_count(logical=True) or 4
                memory_gb = psutil.virtual_memory().total / (1024**3)
            else:
                cpu_cores = 4
                memory_gb = 8.0

            if cpu_cores >= 8 and memory_gb >= 16:
                return "gaming_laptop"
            elif cpu_cores <= 4 and memory_gb <= 8:
                return "ultrabook"
            else:
                return "desktop"
        except Exception:
            return "unknown"

    def _get_capacity_by_device_type(self) -> dict[str, float]:
        capacities = {
            "gaming_laptop": {"cpu": 4.0, "memory": 8192, "disk": 30000},
            "ultrabook": {"cpu": 2.0, "memory": 4096, "disk": 10000},
            "desktop": {"cpu": 6.0, "memory": 12288, "disk": 50000},
            "unknown": {"cpu": 2.0, "memory": 2048, "disk": 10000},
        }
        return capacities.get(self.device_type, capacities["unknown"])

    def _register_task_handlers(self):
        self._message_handlers[MessageType.TASK_REQUEST] = self._handle_task_request
        self._message_handlers[MessageType.TASK_RESULT] = self._handle_task_result

        self.gossip.register_handler("task_broadcast", self._handle_task_broadcast)
        self.gossip.register_handler("result_broadcast", self._handle_result_broadcast)
        self.gossip.register_handler("peer_status", self._handle_peer_status)

    async def start(self) -> bool:
        success = await super().start()
        if not success:
            return False

        self._running = True

        if self._scheduler_mode or self._is_bootstrap:
            print(f"[P2P Scheduler] Running as scheduler on port {self.port}")
        else:
            self._worker_task = asyncio.create_task(self._worker_loop())
            print(f"[P2P Worker] Started, waiting for tasks...")

        asyncio.create_task(self._announce_presence())

        return True

    async def stop(self):
        self._running = False

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        await self.broadcast(
            "peer_status",
            {
                "node_id": self.node_id,
                "status": "offline",
                "timestamp": time.time(),
            },
        )

        await super().stop()

    async def _announce_presence(self):
        while self._running:
            await self.broadcast(
                "peer_status",
                {
                    "node_id": self.node_id,
                    "status": "online",
                    "device_type": self.device_type,
                    "capacity": self.capacity,
                    "is_idle": await self._check_idle(),
                    "timestamp": time.time(),
                },
            )
            await asyncio.sleep(60)

    async def _worker_loop(self):
        print(f"[P2P Worker] Worker loop started")
        while self._running:
            try:
                is_idle, idle_info = await self._check_idle()

                if is_idle and self._running_task is None:
                    task = await self._get_next_task()
                    if task:
                        await self._execute_task(task)

                await asyncio.sleep(self.CHECK_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[P2P Worker] Error in worker loop: {e}")
                await asyncio.sleep(5)

    async def _check_idle(self) -> tuple[bool, dict[str, Any]]:
        try:
            if not PSUTIL_AVAILABLE:
                return True, {"cpu_percent": 30.0, "memory_percent": 50.0, "is_idle": True}

            cpu_percent = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()

            idle_thresholds = {
                "gaming_laptop": {"cpu_threshold": 75.0, "memory_threshold": 85.0},
                "ultrabook": {"cpu_threshold": 70.0, "memory_threshold": 80.0},
                "desktop": {"cpu_threshold": 80.0, "memory_threshold": 90.0},
            }

            thresholds = idle_thresholds.get(self.device_type, idle_thresholds["desktop"])

            is_idle = (
                cpu_percent < thresholds["cpu_threshold"]
                and memory.percent < thresholds["memory_threshold"]
            )

            return is_idle, {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "is_idle": is_idle,
                "device_type": self.device_type,
            }

        except Exception as e:
            print(f"[P2P] Idle check error: {e}")
            return True, {"is_idle": True, "error": str(e)}

    async def _get_next_task(self) -> Optional[Task]:
        if self._task_queue:
            return self._task_queue.pop(0)

        for peer in self.dht.get_all_peers():
            if peer.state == PeerState.ONLINE and peer.capabilities.get("is_scheduler"):
                try:
                    message = Message(
                        type=MessageType.TASK_REQUEST,
                        sender_id=self.node_id,
                        payload={
                            "node_id": self.node_id,
                            "capacity": self.capacity,
                            "device_type": self.device_type,
                        },
                    )

                    reader, writer = await asyncio.open_connection(peer.ip, peer.port)
                    writer.write(message.to_bytes())
                    await writer.drain()

                    data = await reader.read(65536)
                    if data:
                        response = Message.from_bytes(data)
                        task_data = response.payload.get("task")
                        if task_data:
                            return Task(**task_data)

                    writer.close()
                    await writer.wait_closed()

                except Exception:
                    pass

        return None

    async def _execute_task(self, task: Task):
        self._running_task = task
        task.status = "running"
        task.assigned_node = self.node_id

        print(f"[P2P Worker] Executing task {task.task_id}")
        start_time = time.time()

        try:
            result = await self._safe_execute(task.code, task.timeout)
            execution_time = time.time() - start_time

            task_result = TaskResult(
                task_id=task.task_id,
                node_id=self.node_id,
                result=result,
                execution_time=execution_time,
                success=True,
            )

            self._task_count += 1
            self._total_compute_time += execution_time

            await self._broadcast_result(task_result)

            print(f"[P2P Worker] Task {task.task_id} completed in {execution_time:.2f}s")

        except Exception as e:
            execution_time = time.time() - start_time
            task_result = TaskResult(
                task_id=task.task_id,
                node_id=self.node_id,
                result="",
                execution_time=execution_time,
                success=False,
                error=str(e),
            )

            self._error_count += 1
            await self._broadcast_result(task_result)

            print(f"[P2P Worker] Task {task.task_id} failed: {e}")

        finally:
            self._running_task = None

    async def _safe_execute(self, code: str, timeout: int = 300) -> str:
        try:
            try:
                from src.infrastructure.sandbox.security import CodeValidator

                validator = CodeValidator()
                is_valid, errors = validator.validate(code)
                if not is_valid:
                    return f"Code validation failed: {'; '.join(errors)}"
            except ImportError:
                pass

            local_vars = {
                "__builtins__": {
                    "print": print,
                    "range": range,
                    "len": len,
                    "str": str,
                    "int": int,
                    "float": float,
                    "list": list,
                    "dict": dict,
                    "sum": sum,
                    "min": min,
                    "max": max,
                    "abs": abs,
                    "round": round,
                    "sorted": sorted,
                    "enumerate": enumerate,
                    "zip": zip,
                    "map": map,
                    "filter": filter,
                }
            }

            exec_result = []

            def capture_print(*args, **kwargs):
                exec_result.append(" ".join(str(a) for a in args))

            local_vars["__builtins__"]["print"] = capture_print

            exec(code, local_vars, local_vars)

            if "result" in local_vars:
                return str(local_vars["result"])
            elif exec_result:
                return "\n".join(exec_result)
            else:
                return "Execution completed (no output)"

        except Exception as e:
            return f"Execution error: {str(e)}"

    async def _broadcast_result(self, result: TaskResult):
        self._completed_tasks[result.task_id] = result

        await self.broadcast(
            "result_broadcast",
            {
                "task_id": result.task_id,
                "node_id": result.node_id,
                "result": result.result,
                "execution_time": result.execution_time,
                "success": result.success,
                "error": result.error,
            },
        )

    async def submit_task(
        self,
        code: str,
        timeout: int = 300,
        resources: dict = None,
        priority: int = 0,
    ) -> str:
        task_id = hashlib.sha256(f"{code}{time.time()}{uuid.uuid4()}".encode()).hexdigest()[:16]

        task = Task(
            task_id=task_id,
            code=code,
            timeout=timeout,
            required_resources=resources or {"cpu": 1.0, "memory": 512},
            priority=priority,
        )

        self._pending_tasks[task_id] = task

        if self._scheduler_mode or self._is_bootstrap:
            self._task_queue.append(task)
            print(f"[P2P Scheduler] Task {task_id} added to queue")
        else:
            await self.broadcast(
                "task_broadcast",
                {
                    "task_id": task_id,
                    "code": code,
                    "timeout": timeout,
                    "required_resources": task.required_resources,
                    "priority": priority,
                    "sender_id": self.node_id,
                },
            )
            print(f"[P2P Client] Task {task_id} broadcast to network")

        return task_id

    async def get_task_result(self, task_id: str, timeout: float = 60.0) -> Optional[TaskResult]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            if task_id in self._completed_tasks:
                return self._completed_tasks[task_id]
            await asyncio.sleep(1)
        return None

    async def _handle_task_request(self, message: Message, writer: asyncio.StreamWriter = None):
        if not (self._scheduler_mode or self._is_bootstrap):
            return

        if self._task_queue:
            task = self._task_queue.pop(0)
            task.status = "assigned"
            task.assigned_node = message.payload.get("node_id")

            response = Message(
                type=MessageType.TASK_REQUEST,
                sender_id=self.node_id,
                payload={"task": task.__dict__},
            )

            if writer:
                writer.write(response.to_bytes())
                await writer.drain()

    async def _handle_task_result(self, message: Message, writer: asyncio.StreamWriter = None):
        result_data = message.payload
        task_id = result_data.get("task_id")

        if task_id in self._pending_tasks:
            task = self._pending_tasks[task_id]
            task.status = "completed"
            task.result = result_data.get("result")
            task.completed_at = time.time()

            result = TaskResult(
                task_id=task_id,
                node_id=result_data.get("node_id"),
                result=result_data.get("result", ""),
                execution_time=result_data.get("execution_time", 0),
                success=result_data.get("success", True),
                error=result_data.get("error"),
            )

            self._completed_tasks[task_id] = result
            print(f"[P2P Scheduler] Task {task_id} completed by {result.node_id}")

    async def _handle_task_broadcast(self, data: dict):
        if self._scheduler_mode or self._is_bootstrap:
            task = Task(
                task_id=data.get("task_id"),
                code=data.get("code"),
                timeout=data.get("timeout", 300),
                required_resources=data.get("required_resources", {}),
                priority=data.get("priority", 0),
            )
            self._task_queue.append(task)
            self._pending_tasks[task.task_id] = task
            print(f"[P2P Scheduler] Received task {task.task_id} from network")

    async def _handle_result_broadcast(self, data: dict):
        task_id = data.get("task_id")
        if task_id in self._pending_tasks:
            result = TaskResult(
                task_id=task_id,
                node_id=data.get("node_id"),
                result=data.get("result", ""),
                execution_time=data.get("execution_time", 0),
                success=data.get("success", True),
                error=data.get("error"),
            )
            self._completed_tasks[task_id] = result

            task = self._pending_tasks[task_id]
            task.status = "completed"
            task.result = result.result
            task.completed_at = time.time()

    async def _handle_peer_status(self, data: dict):
        node_id = data.get("node_id")
        status = data.get("status")

        if node_id and node_id != self.node_id:
            if status == "offline":
                self.dht.remove_peer(node_id)
                if node_id in self._peers:
                    del self._peers[node_id]
            elif status == "online":
                peer = PeerInfo(
                    node_id=node_id,
                    ip=data.get("ip", "unknown"),
                    port=data.get("port", 8765),
                    capabilities=data.get("capacity", {}),
                    state=PeerState.ONLINE,
                    last_seen=time.time(),
                )
                self.dht.add_peer(peer)
                self._peers[node_id] = peer

    def get_stats(self) -> dict[str, Any]:
        stats = super().get_stats()
        stats.update(
            {
                "device_type": self.device_type,
                "capacity": self.capacity,
                "is_scheduler": self._scheduler_mode or self._is_bootstrap,
                "task_count": self._task_count,
                "error_count": self._error_count,
                "total_compute_time": self._total_compute_time,
                "pending_tasks": len(self._pending_tasks),
                "completed_tasks": len(self._completed_tasks),
                "queue_size": len(self._task_queue),
                "uptime": time.time() - self._start_time,
            }
        )
        return stats

    def print_status(self):
        stats = self.get_stats()
        print("\n" + "=" * 60)
        print("P2P Client Status")
        print("=" * 60)
        print(f"Node ID: {stats['node_id']}")
        print(f"Port: {stats['port']}")
        print(f"Device Type: {stats['device_type']}")
        print(f"Role: {'Scheduler' if stats['is_scheduler'] else 'Worker'}")
        print(f"Peers: {stats['peers']} ({stats['online_peers']} online)")
        print(f"Tasks Completed: {stats['task_count']}")
        print(f"Errors: {stats['error_count']}")
        print(f"Total Compute Time: {stats['total_compute_time']:.1f}s")
        print(f"Uptime: {stats['uptime']:.0f}s")
        print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(description="P2P Computing Client")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    parser.add_argument("--bootstrap", action="store_true", help="Run as bootstrap node")
    parser.add_argument("--scheduler", action="store_true", help="Run as scheduler")
    parser.add_argument(
        "--bootstrap-node",
        type=str,
        help="Bootstrap node address (ip:port)",
    )
    parser.add_argument("--submit", type=str, help="Submit a task and exit")
    parser.add_argument("--node-id", type=str, help="Custom node ID")

    args = parser.parse_args()

    bootstrap_nodes = []
    if args.bootstrap_node:
        try:
            ip, port = args.bootstrap_node.split(":")
            bootstrap_nodes.append((ip, int(port)))
        except ValueError:
            print(f"Invalid bootstrap node format: {args.bootstrap_node}")
            sys.exit(1)

    node_id = args.node_id or hashlib.sha256(
        f"{socket.gethostname()}{time.time()}{uuid.uuid4()}".encode()
    ).hexdigest()[:16]

    client = P2PClient(
        node_id=node_id,
        port=args.port,
        is_bootstrap=args.bootstrap,
        scheduler_mode=args.scheduler,
        bootstrap_nodes=bootstrap_nodes,
    )

    if args.submit:
        if not bootstrap_nodes and not args.bootstrap:
            print("Error: --bootstrap-node required for task submission")
            sys.exit(1)

        await client.start()

        task_id = await client.submit_task(args.submit)
        print(f"Task submitted: {task_id}")

        print("Waiting for result...")
        result = await client.get_task_result(task_id, timeout=120)

        if result:
            print(f"\nResult from {result.node_id}:")
            print(f"  Success: {result.success}")
            print(f"  Execution time: {result.execution_time:.2f}s")
            print(f"  Output: {result.result[:500]}...")
        else:
            print("Timeout waiting for result")

        await client.stop()
        return

    await client.start()

    print("\n" + "=" * 60)
    print("P2P Computing Client Started")
    print("=" * 60)
    print(f"Node ID: {client.node_id}")
    print(f"Port: {client.port}")
    print(f"Role: {'Scheduler/Bootstrap' if (args.bootstrap or args.scheduler) else 'Worker'}")
    print(f"Bootstrap nodes: {bootstrap_nodes or 'None'}")
    print("=" * 60)
    print("\nPress Ctrl+C to stop...")

    try:
        while client._running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        await client.stop()

    client.print_status()


if __name__ == "__main__":
    asyncio.run(main())

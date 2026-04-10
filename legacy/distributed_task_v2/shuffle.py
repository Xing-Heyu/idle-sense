"""
Shuffle Implementation for Distributed Data Processing.

Implements data shuffle operation for wide dependencies in distributed tasks.
Shuffle is the process of redistributing data across nodes based on keys,
similar to MapReduce shuffle phase.

"""

import asyncio
import contextlib
import hashlib
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Optional, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class ShufflePartition:
    """Represents a partition in a shuffle operation."""

    partition_id: int
    key: Any
    values: list[Any] = field(default_factory=list)
    node_id: Optional[str] = None
    size: int = 0

    def __post_init__(self):
        if self.values and self.size == 0:
            self.size = len(self.values)

    def add_value(self, value: Any):
        self.values.append(value)
        self.size += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "partition_id": self.partition_id,
            "key": str(self.key),
            "size": self.size,
            "node_id": self.node_id,
        }


@dataclass
class ShuffleResult:
    """Result of a shuffle operation."""

    shuffle_id: str
    stage_id: str
    task_id: str
    partitions: dict[int, ShufflePartition] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    status: str = "pending"

    @property
    def total_size(self) -> int:
        return sum(p.size for p in self.partitions.values())

    @property
    def is_complete(self) -> bool:
        return all(p.node_id is not None for p in self.partitions.values())


class ShuffleManager(Generic[K, V]):
    """
    Manages shuffle operations for distributed tasks.

    A shuffle operation redistributes data across nodes based on keys.
    This is necessary for wide dependencies in DAG execution.
    """

    def __init__(
        self,
        num_partitions: int = 4,
        hash_func: Callable[[K], int] = None,
        serializer: Callable[[Any], bytes] = None,
        deserializer: Callable[[bytes], Any] = None,
    ):
        self.num_partitions = num_partitions
        self.hash_func = hash_func or self._default_hash
        self.serializer = serializer or self._default_serialize
        self.deserializer = deserializer or self._default_deserialize

        self._shuffle_results: dict[str, ShuffleResult] = {}
        self._pending_data: dict[str, list[tuple[Any, Any]]] = defaultdict(list)
        self._stats = {
            "shuffles_started": 0,
            "shuffles_completed": 0,
            "total_records_shuffled": 0,
            "total_bytes_transferred": 0,
        }

    @staticmethod
    def _default_hash(key: K) -> int:
        return int(hashlib.md5(str(key).encode()).hexdigest(), 16)

    @staticmethod
    def _default_serialize(data: Any) -> bytes:
        import json

        return json.dumps(data).encode()

    @staticmethod
    def _default_deserialize(data: bytes) -> Any:
        import json

        return json.loads(data.decode())

    def get_partition_id(self, key: K) -> int:
        """Get the partition ID for a key."""
        return self.hash_func(key) % self.num_partitions

    def start_shuffle(self, task_id: str, stage_id: str) -> str:
        """Start a new shuffle operation."""
        shuffle_id = hashlib.md5(f"{task_id}:{stage_id}:{time.time()}".encode()).hexdigest()[:16]

        result = ShuffleResult(
            shuffle_id=shuffle_id,
            stage_id=stage_id,
            task_id=task_id,
            partitions={
                i: ShufflePartition(partition_id=i, key=None) for i in range(self.num_partitions)
            },
        )

        self._shuffle_results[shuffle_id] = result
        self._stats["shuffles_started"] += 1

        return shuffle_id

    def add_data(self, shuffle_id: str, key: K, value: V):
        """Add data to a shuffle operation."""
        if shuffle_id not in self._shuffle_results:
            return False

        result = self._shuffle_results[shuffle_id]
        partition_id = self.get_partition_id(key)

        if partition_id not in result.partitions:
            partition = ShufflePartition(partition_id=partition_id, key=key)
            partition.add_value(value)
            result.partitions[partition_id] = partition
        else:
            result.partitions[partition_id].add_value(value)

        self._stats["total_records_shuffled"] += 1
        return True

    def get_partition(self, shuffle_id: str, partition_id: int) -> Optional[ShufflePartition]:
        """Get a partition from a shuffle operation."""
        if shuffle_id not in self._shuffle_results:
            return None

        result = self._shuffle_results[shuffle_id]
        return result.partitions.get(partition_id)

    def assign_partition(self, shuffle_id: str, partition_id: int, node_id: str) -> bool:
        """Assign a partition to a node for processing."""
        if shuffle_id not in self._shuffle_results:
            return False

        result = self._shuffle_results[shuffle_id]
        if partition_id in result.partitions:
            result.partitions[partition_id].node_id = node_id
            return True
        return False

    def complete_shuffle(self, shuffle_id: str) -> bool:
        """Mark a shuffle operation as complete."""
        if shuffle_id not in self._shuffle_results:
            return False

        result = self._shuffle_results[shuffle_id]
        result.status = "completed"
        result.completed_at = time.time()
        self._stats["shuffles_completed"] += 1
        return True

    def get_shuffle_result(self, shuffle_id: str) -> Optional[ShuffleResult]:
        """Get the shuffle result."""
        return self._shuffle_results.get(shuffle_id)

    def get_stats(self) -> dict[str, Any]:
        """Get shuffle statistics."""
        return {
            **self._stats,
            "active_shuffles": len(
                [s for s in self._shuffle_results.values() if s.status == "pending"]
            ),
        }


class ShuffleExecutor:
    """Executes shuffle operations across nodes."""

    def __init__(
        self,
        shuffle_manager: ShuffleManager,
        send_func: Callable[[str, bytes], bool],
        receive_func: Callable[[str], bytes],
    ):
        self.manager = shuffle_manager
        self.send_func = send_func
        self.receive_func = receive_func
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self):
        """Start the shuffle executor."""
        if self._running:
            return

        self._running = True
        self._tasks = [
            asyncio.create_task(self._run_shuffle_loop()),
        ]

    async def stop(self):
        """Stop the shuffle executor."""
        self._running = False
        for task in self._tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks = []

    async def _run_shuffle_loop(self):
        """Background loop for processing shuffle operations."""
        while self._running:
            await asyncio.sleep(0.1)

    async def execute_shuffle(
        self, shuffle_id: str, source_node: str, target_nodes: list[str]
    ) -> bool:
        """Execute a shuffle operation from source to target nodes."""
        result = self.manager.get_shuffle_result(shuffle_id)
        if not result:
            return False

        for _, partition in result.partitions.items():
            if partition.node_id is None:
                continue

            data_bytes = self.manager.serializer(partition.values)
            self.manager._stats["total_bytes_transferred"] += len(data_bytes)

            success = await self.send_func(partition.node_id, data_bytes)
            if not success:
                return False

        self.manager.complete_shuffle(shuffle_id)
        return True

    async def receive_shuffle_data(self, shuffle_id: str, partition_id: int, data: bytes) -> bool:
        """Receive shuffle data from another node."""
        partition = self.manager.get_partition(shuffle_id, partition_id)
        if not partition:
            return False

        values = self.manager.deserializer(data)
        partition.values.extend(values)
        return True


__all__ = [
    "ShufflePartition",
    "ShuffleResult",
    "ShuffleManager",
    "ShuffleExecutor",
]

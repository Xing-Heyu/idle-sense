"""
DHT Replication Module.

Implements data replication for the Kademlia DHT:
- Replication factor for fault tolerance
- Periodic data refresh
- Republishing mechanism
- Data consistency checks

References:
- Kademlia: Maymounkov & Mazieres, "A Peer-to-Peer Information System" (2002)
- Chord: Stoica et al., "Chord: A Scalable Peer-to-peer Lookup Service" (2001)
"""

import asyncio
import contextlib
import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class ReplicationStatus(Enum):
    PENDING = "pending"
    REPLICATING = "replicating"
    REPLICATED = "replicated"
    FAILED = "failed"


@dataclass
class ReplicatedValue:
    """A value stored in the DHT with replication metadata."""

    key: str
    value: Any
    original_publisher: str
    timestamp: float
    ttl: float
    replication_factor: int = 3
    replicas: list[str] = field(default_factory=list)
    status: ReplicationStatus = ReplicationStatus.PENDING
    last_refresh: float = field(default_factory=time.time)
    version: int = 1

    def is_expired(self) -> bool:
        """Check if the value has expired."""
        return time.time() > self.timestamp + self.ttl

    def needs_refresh(self, refresh_interval: float = 3600) -> bool:
        """Check if the value needs to be refreshed."""
        return time.time() - self.last_refresh > refresh_interval

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "key": self.key,
            "value": self.value,
            "original_publisher": self.original_publisher,
            "timestamp": self.timestamp,
            "ttl": self.ttl,
            "replication_factor": self.replication_factor,
            "replicas": self.replicas,
            "status": self.status.value,
            "last_refresh": self.last_refresh,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReplicatedValue":
        """Deserialize from dictionary."""
        return cls(
            key=data["key"],
            value=data["value"],
            original_publisher=data["original_publisher"],
            timestamp=data["timestamp"],
            ttl=data["ttl"],
            replication_factor=data.get("replication_factor", 3),
            replicas=data.get("replicas", []),
            status=ReplicationStatus(data.get("status", "pending")),
            last_refresh=data.get("last_refresh", time.time()),
            version=data.get("version", 1),
        )


@dataclass
class ReplicationTask:
    """A task for replicating data to other nodes."""

    key: str
    value: Any
    target_nodes: list[str]
    completed_nodes: list[str] = field(default_factory=list)
    failed_nodes: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    max_retries: int = 3
    retry_count: int = 0

    @property
    def is_complete(self) -> bool:
        return len(self.completed_nodes) >= len(self.target_nodes)

    @property
    def success_count(self) -> int:
        return len(self.completed_nodes)


class DHTReplicationManager:
    """
    Manages DHT data replication.

    Features:
    - Configurable replication factor
    - Automatic data refresh
    - Failure recovery
    - Consistency checks
    """

    DEFAULT_REPLICATION_FACTOR = 3
    REFRESH_INTERVAL = 3600
    REPLICATION_TIMEOUT = 30.0
    MAX_PENDING_TASKS = 1000

    def __init__(
        self,
        node_id: str,
        replication_factor: int = None,
        send_func: Callable = None,
        find_nodes_func: Callable = None,
    ):
        self.node_id = node_id
        self.replication_factor = replication_factor or self.DEFAULT_REPLICATION_FACTOR
        self.send_func = send_func
        self.find_nodes_func = find_nodes_func

        self.local_storage: dict[str, ReplicatedValue] = {}
        self.pending_replications: OrderedDict[str, ReplicationTask] = OrderedDict()
        self.replica_index: dict[str, list[str]] = {}

        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._stats = {
            "total_stored": 0,
            "total_replicated": 0,
            "replication_failures": 0,
            "refresh_count": 0,
        }

    async def start(self):
        """Start the replication manager."""
        if self._running:
            return

        self._running = True
        self._tasks = [
            asyncio.create_task(self._run_refresh_loop()),
            asyncio.create_task(self._run_replication_loop()),
            asyncio.create_task(self._run_cleanup_loop()),
        ]

    async def stop(self):
        """Stop the replication manager."""
        self._running = False
        for task in self._tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks = []

    async def store(self, key: str, value: Any, ttl: float = 86400, replicate: bool = True) -> bool:
        """
        Store a value in the DHT with replication.

        Args:
            key: The key to store
            value: The value to store
            ttl: Time to live in seconds
            replicate: Whether to replicate to other nodes

        Returns:
            True if stored successfully
        """
        replicated_value = ReplicatedValue(
            key=key,
            value=value,
            original_publisher=self.node_id,
            timestamp=time.time(),
            ttl=ttl,
            replication_factor=self.replication_factor,
        )

        self.local_storage[key] = replicated_value
        self._stats["total_stored"] += 1

        if replicate and self.send_func and self.find_nodes_func:
            await self._initiate_replication(key, value, ttl)

        return True

    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the DHT.

        Args:
            key: The key to retrieve

        Returns:
            The value if found, None otherwise
        """
        if key in self.local_storage:
            value = self.local_storage[key]
            if not value.is_expired():
                return value.value
            else:
                del self.local_storage[key]

        return None

    async def delete(self, key: str) -> bool:
        """
        Delete a value from the DHT.

        Args:
            key: The key to delete

        Returns:
            True if deleted successfully
        """
        if key in self.local_storage:
            del self.local_storage[key]
            return True
        return False

    async def receive_replica(
        self,
        key: str,
        value: Any,
        original_publisher: str,
        timestamp: float,
        ttl: float,
        version: int = 1,
    ) -> bool:
        """
        Receive a replica from another node.

        Args:
            key: The key being replicated
            value: The value
            original_publisher: Original publisher node ID
            timestamp: Original timestamp
            ttl: Time to live
            version: Version number

        Returns:
            True if accepted
        """
        if key in self.local_storage:
            existing = self.local_storage[key]
            if existing.version >= version and existing.timestamp >= timestamp:
                return False

        replicated_value = ReplicatedValue(
            key=key,
            value=value,
            original_publisher=original_publisher,
            timestamp=timestamp,
            ttl=ttl,
            replication_factor=self.replication_factor,
            status=ReplicationStatus.REPLICATED,
            version=version,
        )

        self.local_storage[key] = replicated_value
        self._stats["total_replicated"] += 1

        return True

    async def _initiate_replication(self, key: str, value: Any, ttl: float):
        """Initiate replication of a value to closest nodes."""
        if not self.find_nodes_func:
            return

        try:
            closest_nodes = await self.find_nodes_func(key, count=self.replication_factor)

            target_nodes = [node.node_id for node in closest_nodes if node.node_id != self.node_id]

            if not target_nodes:
                return

            task = ReplicationTask(
                key=key,
                value=value,
                target_nodes=target_nodes[: self.replication_factor],
            )

            self.pending_replications[key] = task

            while len(self.pending_replications) > self.MAX_PENDING_TASKS:
                self.pending_replications.popitem(last=False)

        except Exception as e:
            print(f"[DHT Replication] Failed to initiate replication for {key}: {e}")

    async def _run_replication_loop(self):
        """Process pending replication tasks."""
        while self._running:
            await asyncio.sleep(1)

            if not self.send_func:
                continue

            completed_keys = []

            for key, task in list(self.pending_replications.items()):
                if task.is_complete:
                    completed_keys.append(key)
                    if key in self.local_storage:
                        self.local_storage[key].status = ReplicationStatus.REPLICATED
                        self.local_storage[key].replicas = task.completed_nodes
                    continue

                remaining_nodes = [
                    n
                    for n in task.target_nodes
                    if n not in task.completed_nodes and n not in task.failed_nodes
                ]

                for node_id in remaining_nodes[:3]:
                    try:
                        success = await self._send_replica(node_id, task.key, task.value)
                        if success:
                            task.completed_nodes.append(node_id)
                        else:
                            task.failed_nodes.append(node_id)
                    except Exception:
                        task.failed_nodes.append(node_id)

                if len(task.failed_nodes) > 0 and task.retry_count < task.max_retries:
                    task.retry_count += 1
                    task.failed_nodes.clear()

                if time.time() - task.started_at > self.REPLICATION_TIMEOUT:
                    completed_keys.append(key)
                    self._stats["replication_failures"] += 1

            for key in completed_keys:
                self.pending_replications.pop(key, None)

    async def _send_replica(self, node_id: str, key: str, value: Any) -> bool:
        """Send a replica to a specific node."""
        if not self.send_func:
            return False

        try:
            stored_value = self.local_storage.get(key)
            if not stored_value:
                return False

            message = {
                "type": "store_replica",
                "key": key,
                "value": value,
                "original_publisher": stored_value.original_publisher,
                "timestamp": stored_value.timestamp,
                "ttl": stored_value.ttl,
                "version": stored_value.version,
            }

            return await self.send_func(node_id, message)
        except Exception:
            return False

    async def _run_refresh_loop(self):
        """Periodically refresh stored values."""
        while self._running:
            await asyncio.sleep(self.REFRESH_INTERVAL / 2)

            keys_to_refresh = []

            for key, value in self.local_storage.items():
                if value.original_publisher == self.node_id and value.needs_refresh(
                    self.REFRESH_INTERVAL
                ):
                    keys_to_refresh.append(key)

            for key in keys_to_refresh:
                try:
                    value = self.local_storage[key]
                    if not value.is_expired():
                        await self._initiate_replication(key, value.value, value.ttl)
                        value.last_refresh = time.time()
                        value.version += 1
                        self._stats["refresh_count"] += 1
                except Exception as e:
                    print(f"[DHT Replication] Failed to refresh {key}: {e}")

    async def _run_cleanup_loop(self):
        """Clean up expired values."""
        while self._running:
            await asyncio.sleep(300)

            expired_keys = [key for key, value in self.local_storage.items() if value.is_expired()]

            for key in expired_keys:
                del self.local_storage[key]
                self.replica_index.pop(key, None)

    def get_stats(self) -> dict[str, Any]:
        """Get replication statistics."""
        return {
            **self._stats,
            "local_storage_count": len(self.local_storage),
            "pending_replications": len(self.pending_replications),
            "replication_factor": self.replication_factor,
            "running": self._running,
        }

    def get_storage_info(self) -> list[dict[str, Any]]:
        """Get information about all stored values."""
        return [value.to_dict() for value in self.local_storage.values() if not value.is_expired()]


class ConsistentHashRing:
    """
    Consistent hash ring for data partitioning.

    Used to determine which nodes are responsible for storing
    specific keys in a distributed manner.
    """

    VIRTUAL_NODES = 150

    def __init__(self, virtual_nodes: int = None):
        self.virtual_nodes = virtual_nodes or self.VIRTUAL_NODES
        self.ring: dict[int, str] = {}
        self.sorted_keys: list[int] = []

    def _hash(self, key: str) -> int:
        """Generate a consistent hash for a key."""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_node(self, node_id: str):
        """Add a node to the ring."""
        for i in range(self.virtual_nodes):
            virtual_key = f"{node_id}:{i}"
            hash_key = self._hash(virtual_key)
            self.ring[hash_key] = node_id

        self.sorted_keys = sorted(self.ring.keys())

    def remove_node(self, node_id: str):
        """Remove a node from the ring."""
        keys_to_remove = [k for k, v in self.ring.items() if v == node_id]

        for key in keys_to_remove:
            del self.ring[key]

        self.sorted_keys = sorted(self.ring.keys())

    def get_node(self, key: str) -> Optional[str]:
        """Get the node responsible for a key."""
        if not self.ring:
            return None

        hash_key = self._hash(key)

        for ring_key in self.sorted_keys:
            if hash_key <= ring_key:
                return self.ring[ring_key]

        return self.ring[self.sorted_keys[0]]

    def get_nodes(self, key: str, count: int = 3) -> list[str]:
        """Get multiple nodes responsible for a key (for replication)."""
        if not self.ring:
            return []

        hash_key = self._hash(key)
        nodes = []
        seen_nodes = set()

        start_idx = 0
        for i, ring_key in enumerate(self.sorted_keys):
            if hash_key <= ring_key:
                start_idx = i
                break
        else:
            start_idx = 0

        for i in range(len(self.sorted_keys)):
            idx = (start_idx + i) % len(self.sorted_keys)
            ring_key = self.sorted_keys[idx]
            node = self.ring[ring_key]

            if node not in seen_nodes:
                nodes.append(node)
                seen_nodes.add(node)

                if len(nodes) >= count:
                    break

        return nodes


__all__ = [
    "ReplicationStatus",
    "ReplicatedValue",
    "ReplicationTask",
    "DHTReplicationManager",
    "ConsistentHashRing",
]

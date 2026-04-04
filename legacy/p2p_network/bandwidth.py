"""
Bandwidth Limiting and Traffic Control.

Implements:
- Token bucket algorithm for rate limiting
- Per-connection bandwidth limits
- Global bandwidth management
- Traffic statistics

References:
- Token Bucket: Turner, "New Directions in Communications" (1986)
"""

import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional


class TrafficPriority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class BandwidthConfig:
    """Configuration for bandwidth limiting."""
    max_upload_bytes_per_sec: int = 1024 * 1024
    max_download_bytes_per_sec: int = 10 * 1024 * 1024
    max_connections: int = 100
    burst_size: int = 64 * 1024
    token_refill_rate: float = 0.1
    min_bucket_size: int = 1024
    max_bucket_size: int = 1024 * 1024


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    capacity: int
    refill_rate: float
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.time)

    def refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.refill_rate
        )
        self.last_refill = now

    def consume(self, amount: int) -> bool:
        """Try to consume tokens."""
        self.refill()
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    def wait_time(self, amount: int) -> float:
        """Calculate time to wait for enough tokens."""
        self.refill()
        if self.tokens >= amount:
            return 0.0
        needed = amount - self.tokens
        return needed / self.refill_rate


@dataclass
class ConnectionStats:
    """Statistics for a connection."""
    connection_id: str
    bytes_sent: int = 0
    bytes_received: int = 0
    packets_sent: int = 0
    packets_received: int = 0
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    @property
    def total_bytes(self) -> int:
        return self.bytes_sent + self.bytes_received

    @property
    def age(self) -> float:
        return time.time() - self.created_at

    @property
    def idle_time(self) -> float:
        return time.time() - self.last_activity


class BandwidthManager:
    """
    Manages bandwidth for network connections.
    
    Features:
    - Token bucket rate limiting
    - Per-connection limits
    - Global bandwidth management
    - Traffic statistics
    """

    def __init__(self, config: BandwidthConfig = None):
        self.config = config or BandwidthConfig()

        self.upload_bucket = TokenBucket(
            capacity=self.config.max_bucket_size,
            refill_rate=self.config.token_refill_rate
        )
        self.download_bucket = TokenBucket(
            capacity=self.config.max_bucket_size,
            refill_rate=self.config.token_refill_rate
        )

        self._connections: dict[str, ConnectionStats] = {}
        self._connection_buckets: dict[str, TokenBucket] = {}

        self._stats = {
            "total_bytes_sent": 0,
            "total_bytes_received": 0,
            "total_packets_sent": 0,
            "total_packets_received": 0,
            "throttled_count": 0,
            "connections_created": 0,
        }

    def register_connection(self, connection_id: str):
        """Register a new connection."""
        if len(self._connections) >= self.config.max_connections:
            return False

        self._connections[connection_id] = ConnectionStats(connection_id=connection_id)
        self._connection_buckets[connection_id] = TokenBucket(
            capacity=self.config.burst_size,
            refill_rate=self.config.token_refill_rate
        )
        self._stats["connections_created"] += 1
        return True

    def unregister_connection(self, connection_id: str):
        """Unregister a connection."""
        self._connections.pop(connection_id, None)
        self._connection_buckets.pop(connection_id, None)

    def can_send(self, size: int, connection_id: str = None) -> bool:
        """Check if we can send data."""
        if not self.upload_bucket.consume(size):
            self._stats["throttled_count"] += 1
            return False

        if connection_id and connection_id in self._connection_buckets and not self._connection_buckets[connection_id].consume(size):
            return False

        return True

    def can_receive(self, size: int, connection_id: str = None) -> bool:
        """Check if we can receive data."""
        if not self.download_bucket.consume(size):
            return False

        if connection_id and connection_id in self._connection_buckets and not self._connection_buckets[connection_id].consume(size):
            return False

        return True

    def record_send(self, size: int, connection_id: str = None):
        """Record sent data."""
        self._stats["total_bytes_sent"] += size
        self._stats["total_packets_sent"] += 1

        if connection_id and connection_id in self._connections:
            conn = self._connections[connection_id]
            conn.bytes_sent += size
            conn.packets_sent += 1
            conn.last_activity = time.time()

    def record_receive(self, size: int, connection_id: str = None):
        """Record received data."""
        self._stats["total_bytes_received"] += size
        self._stats["total_packets_received"] += 1

        if connection_id and connection_id in self._connections:
            conn = self._connections[connection_id]
            conn.bytes_received += size
            conn.packets_received += 1
            conn.last_activity = time.time()

    def get_wait_time(self, size: int, direction: str = "upload") -> float:
        """Get time to wait before sending/receiving."""
        if direction == "upload":
            return self.upload_bucket.wait_time(size)
        else:
            return self.download_bucket.wait_time(size)

    def get_connection_stats(self, connection_id: str) -> Optional[ConnectionStats]:
        """Get statistics for a connection."""
        return self._connections.get(connection_id)

    def get_all_connection_stats(self) -> dict[str, ConnectionStats]:
        """Get statistics for all connections."""
        return self._connections.copy()

    def get_stats(self) -> dict[str, Any]:
        """Get global bandwidth statistics."""
        return {
            **self._stats,
            "active_connections": len(self._connections),
            "upload_tokens": self.upload_bucket.tokens,
            "download_tokens": self.download_bucket.tokens,
        }

    def cleanup_idle_connections(self, max_idle_time: float = 300.0):
        """Remove idle connections."""
        now = time.time()
        idle_connections = [
            conn_id for conn_id, conn in self._connections.items()
            if now - conn.last_activity > max_idle_time
        ]
        for conn_id in idle_connections:
            self.unregister_connection(conn_id)
        return len(idle_connections)


__all__ = [
    "TrafficPriority",
    "BandwidthConfig",
    "TokenBucket",
    "ConnectionStats",
    "BandwidthManager",
]

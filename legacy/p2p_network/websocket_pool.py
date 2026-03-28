"""
WebSocket Connection Pool for P2P Network.

Implements efficient WebSocket connection management:
- Connection pooling and reuse
- Automatic reconnection
- Health monitoring
- Load balancing across connections

References:
- WebSocket Protocol: RFC 6455
- Connection Pooling: "TCP/IP Illustrated" (Stevens, 1994)
"""

import asyncio
import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class ConnectionState(Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    CLOSING = "closing"


@dataclass
class PooledConnection:
    """A pooled WebSocket connection."""
    connection_id: str
    peer_id: str
    peer_address: tuple[str, int]
    state: ConnectionState = ConnectionState.DISCONNECTED
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    last_error: Optional[str] = None
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    reconnect_attempts: int = 0
    max_reconnect_attempts: int = 5

    @property
    def age(self) -> float:
        return time.time() - self.created_at

    @property
    def idle_time(self) -> float:
        return time.time() - self.last_used

    @property
    def is_healthy(self) -> bool:
        return self.state == ConnectionState.CONNECTED

    def record_send(self, size: int):
        self.messages_sent += 1
        self.bytes_sent += size
        self.last_used = time.time()

    def record_receive(self, size: int):
        self.messages_received += 1
        self.bytes_received += size
        self.last_used = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "peer_id": self.peer_id,
            "peer_address": self.peer_address,
            "state": self.state.value,
            "age": round(self.age, 2),
            "idle_time": round(self.idle_time, 2),
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "reconnect_attempts": self.reconnect_attempts,
        }


@dataclass
class PoolConfig:
    """Configuration for connection pool."""
    max_connections: int = 100
    max_connections_per_peer: int = 3
    idle_timeout: float = 300.0
    connect_timeout: float = 10.0
    reconnect_delay: float = 1.0
    max_reconnect_attempts: int = 5
    health_check_interval: float = 30.0
    max_message_size: int = 10 * 1024 * 1024


class WebSocketConnectionPool:
    """
    Manages a pool of WebSocket connections.
    
    Features:
    - Connection pooling and reuse
    - Automatic reconnection
    - Health monitoring
    - Load balancing
    """

    def __init__(self, config: PoolConfig = None):
        self.config = config or PoolConfig()

        self._connections: dict[str, PooledConnection] = {}
        self._peer_connections: dict[str, list[str]] = {}
        self._available: OrderedDict[str, None] = OrderedDict()

        self._message_handlers: dict[str, Callable] = {}
        self._connect_func: Optional[Callable] = None
        self._disconnect_func: Optional[Callable] = None

        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._lock = asyncio.Lock()

        self._stats = {
            "connections_created": 0,
            "connections_closed": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "reconnects": 0,
            "errors": 0,
        }

    async def start(self):
        """Start the connection pool."""
        if self._running:
            return

        self._running = True
        self._tasks = [
            asyncio.create_task(self._run_health_check()),
            asyncio.create_task(self._run_cleanup()),
        ]

    async def stop(self):
        """Stop the connection pool."""
        self._running = False

        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        for conn in list(self._connections.values()):
            await self._close_connection(conn.connection_id)

        self._connections.clear()
        self._peer_connections.clear()
        self._available.clear()

    def set_connect_func(self, func: Callable):
        """Set the function to create new connections."""
        self._connect_func = func

    def set_disconnect_func(self, func: Callable):
        """Set the function to close connections."""
        self._disconnect_func = func

    def register_handler(self, message_type: str, handler: Callable):
        """Register a message handler."""
        self._message_handlers[message_type] = handler

    async def get_connection(
        self,
        peer_id: str,
        peer_address: tuple[str, int]
    ) -> Optional[PooledConnection]:
        """
        Get or create a connection to a peer.
        
        Args:
            peer_id: The peer's identifier
            peer_address: The peer's (host, port)
            
        Returns:
            A pooled connection or None
        """
        async with self._lock:
            existing = self._get_available_connection(peer_id)
            if existing:
                return existing

            if not self._can_create_connection(peer_id):
                return None

            return await self._create_connection(peer_id, peer_address)

    def _get_available_connection(self, peer_id: str) -> Optional[PooledConnection]:
        """Get an available connection for a peer."""
        conn_ids = self._peer_connections.get(peer_id, [])

        for conn_id in conn_ids:
            conn = self._connections.get(conn_id)
            if conn and conn.is_healthy:
                if conn_id in self._available:
                    del self._available[conn_id]
                return conn

        return None

    def _can_create_connection(self, peer_id: str) -> bool:
        """Check if we can create a new connection."""
        if len(self._connections) >= self.config.max_connections:
            return False

        peer_conns = self._peer_connections.get(peer_id, [])
        if len(peer_conns) >= self.config.max_connections_per_peer:
            return False

        return True

    async def _create_connection(
        self,
        peer_id: str,
        peer_address: tuple[str, int]
    ) -> Optional[PooledConnection]:
        """Create a new connection."""
        conn_id = hashlib.md5(
            f"{peer_id}:{peer_address}:{time.time()}".encode()
        ).hexdigest()[:16]

        conn = PooledConnection(
            connection_id=conn_id,
            peer_id=peer_id,
            peer_address=peer_address,
            state=ConnectionState.CONNECTING,
        )

        self._connections[conn_id] = conn

        if peer_id not in self._peer_connections:
            self._peer_connections[peer_id] = []
        self._peer_connections[peer_id].append(conn_id)

        self._stats["connections_created"] += 1

        if self._connect_func:
            try:
                success = await asyncio.wait_for(
                    self._connect_func(peer_id, peer_address),
                    timeout=self.config.connect_timeout
                )

                if success:
                    conn.state = ConnectionState.CONNECTED
                    return conn
                else:
                    conn.state = ConnectionState.ERROR
                    conn.last_error = "Connection failed"
                    self._stats["errors"] += 1
                    return None

            except asyncio.TimeoutError:
                conn.state = ConnectionState.ERROR
                conn.last_error = "Connection timeout"
                self._stats["errors"] += 1
                return None
        else:
            conn.state = ConnectionState.CONNECTED
            return conn

    async def release_connection(self, conn_id: str):
        """Release a connection back to the pool."""
        async with self._lock:
            if conn_id in self._connections:
                conn = self._connections[conn_id]
                if conn.is_healthy:
                    self._available[conn_id] = None

    async def close_connection(self, conn_id: str):
        """Close a specific connection."""
        async with self._lock:
            await self._close_connection(conn_id)

    async def _close_connection(self, conn_id: str):
        """Internal close connection."""
        conn = self._connections.get(conn_id)
        if not conn:
            return

        conn.state = ConnectionState.CLOSING

        if self._disconnect_func:
            try:
                await self._disconnect_func(conn.peer_id, conn.peer_address)
            except Exception:
                pass

        conn.state = ConnectionState.DISCONNECTED

        if conn_id in self._available:
            del self._available[conn_id]

        if conn.peer_id in self._peer_connections:
            try:
                self._peer_connections[conn.peer_id].remove(conn_id)
            except ValueError:
                pass

        del self._connections[conn_id]
        self._stats["connections_closed"] += 1

    async def send_message(
        self,
        conn_id: str,
        message: bytes,
        message_type: str = None
    ) -> bool:
        """Send a message through a connection."""
        conn = self._connections.get(conn_id)
        if not conn or not conn.is_healthy:
            return False

        if len(message) > self.config.max_message_size:
            return False

        conn.record_send(len(message))
        self._stats["messages_sent"] += 1

        return True

    async def broadcast(
        self,
        message: bytes,
        peer_ids: list[str] = None
    ) -> int:
        """
        Broadcast a message to multiple peers.
        
        Args:
            message: The message to send
            peer_ids: Optional list of target peer IDs
            
        Returns:
            Number of successful sends
        """
        success_count = 0

        targets = peer_ids or list(self._peer_connections.keys())

        for peer_id in targets:
            conn = self._get_available_connection(peer_id)
            if conn:
                if await self.send_message(conn.connection_id, message):
                    success_count += 1

        return success_count

    async def reconnect(self, conn_id: str) -> bool:
        """Attempt to reconnect a failed connection."""
        conn = self._connections.get(conn_id)
        if not conn:
            return False

        if conn.reconnect_attempts >= conn.max_reconnect_attempts:
            await self._close_connection(conn_id)
            return False

        conn.reconnect_attempts += 1
        conn.state = ConnectionState.CONNECTING

        if self._connect_func:
            try:
                await asyncio.sleep(
                    self.config.reconnect_delay * conn.reconnect_attempts
                )

                success = await asyncio.wait_for(
                    self._connect_func(conn.peer_id, conn.peer_address),
                    timeout=self.config.connect_timeout
                )

                if success:
                    conn.state = ConnectionState.CONNECTED
                    conn.reconnect_attempts = 0
                    self._stats["reconnects"] += 1
                    return True
                else:
                    conn.state = ConnectionState.ERROR
                    return False

            except Exception:
                conn.state = ConnectionState.ERROR
                return False

        return False

    async def _run_health_check(self):
        """Periodic health check for connections."""
        while self._running:
            await asyncio.sleep(self.config.health_check_interval)

            for conn_id, conn in list(self._connections.items()):
                if conn.state == ConnectionState.ERROR:
                    await self.reconnect(conn_id)
                elif conn.state == ConnectionState.CONNECTED:
                    if conn.idle_time > self.config.idle_timeout:
                        await self.release_connection(conn_id)

    async def _run_cleanup(self):
        """Cleanup idle connections."""
        while self._running:
            await asyncio.sleep(60)

            async with self._lock:
                expired = [
                    conn_id for conn_id, conn in self._connections.items()
                    if conn.idle_time > self.config.idle_timeout * 2
                ]

                for conn_id in expired:
                    await self._close_connection(conn_id)

    def get_connection_stats(self, conn_id: str) -> Optional[dict[str, Any]]:
        """Get statistics for a connection."""
        conn = self._connections.get(conn_id)
        if conn:
            return conn.to_dict()
        return None

    def get_all_connections(self) -> list[dict[str, Any]]:
        """Get all connection information."""
        return [conn.to_dict() for conn in self._connections.values()]

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics."""
        return {
            **self._stats,
            "active_connections": len(self._connections),
            "available_connections": len(self._available),
            "peers_connected": len(self._peer_connections),
            "running": self._running,
        }

    def get_peer_stats(self) -> dict[str, int]:
        """Get connection count per peer."""
        return {
            peer_id: len(conns)
            for peer_id, conns in self._peer_connections.items()
        }


class ConnectionLoadBalancer:
    """
    Load balancer for distributing load across connections.
    """

    def __init__(self, pool: WebSocketConnectionPool):
        self.pool = pool
        self._round_robin_index = 0

    def select_connection(
        self,
        peer_id: str,
        strategy: str = "round_robin"
    ) -> Optional[PooledConnection]:
        """
        Select a connection using the specified strategy.
        
        Args:
            peer_id: The peer to connect to
            strategy: Selection strategy (round_robin, least_used, random)
            
        Returns:
            Selected connection or None
        """
        conn_ids = self.pool._peer_connections.get(peer_id, [])
        if not conn_ids:
            return None

        healthy_conns = [
            self.pool._connections[cid]
            for cid in conn_ids
            if cid in self.pool._connections and
            self.pool._connections[cid].is_healthy
        ]

        if not healthy_conns:
            return None

        if strategy == "round_robin":
            self._round_robin_index = (self._round_robin_index + 1) % len(healthy_conns)
            return healthy_conns[self._round_robin_index]

        elif strategy == "least_used":
            return min(healthy_conns, key=lambda c: c.messages_sent)

        elif strategy == "random":
            import random
            return random.choice(healthy_conns)

        else:
            return healthy_conns[0]


__all__ = [
    "ConnectionState",
    "PooledConnection",
    "PoolConfig",
    "WebSocketConnectionPool",
    "ConnectionLoadBalancer",
]

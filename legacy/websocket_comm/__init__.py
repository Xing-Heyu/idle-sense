"""
WebSocket communication module for real-time node-scheduler communication.

This module provides WebSocket-based communication for lower latency
and better real-time updates compared to HTTP polling.

Architecture Reference:
- WebSocket Protocol (RFC 6455)
- FastAPI WebSocket support
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

try:
    from fastapi import WebSocket, WebSocketDisconnect

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    WebSocket = None
    WebSocketDisconnect = Exception


class MessageType(str, Enum):
    """WebSocket message types."""

    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    TASK_ASSIGNED = "task_assigned"
    TASK_RESULT = "task_result"
    NODE_STATUS = "node_status"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


@dataclass
class WebSocketMessage:
    """WebSocket message structure."""

    type: MessageType
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    message_id: Optional[str] = None

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(
            {
                "type": self.type.value if isinstance(self.type, MessageType) else self.type,
                "payload": self.payload,
                "timestamp": self.timestamp,
                "message_id": self.message_id,
            }
        )

    @classmethod
    def from_json(cls, data: str) -> "WebSocketMessage":
        """Deserialize from JSON string."""
        obj = json.loads(data)
        return cls(
            type=MessageType(obj["type"]),
            payload=obj.get("payload", {}),
            timestamp=obj.get("timestamp", time.time()),
            message_id=obj.get("message_id"),
        )


class ConnectionManager:
    """
    WebSocket connection manager for handling multiple node connections.

    Usage:
        manager = ConnectionManager()

        @app.websocket("/ws/node/{node_id}")
        async def websocket_endpoint(websocket: WebSocket, node_id: str):
            await manager.connect(node_id, websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    await manager.handle_message(node_id, data)
            except WebSocketDisconnect:
                manager.disconnect(node_id)
    """

    def __init__(
        self, heartbeat_interval: int = 30, heartbeat_timeout: int = 90, max_connections: int = 1000
    ):
        self.active_connections: dict[str, WebSocket] = {}
        self.connection_metadata: dict[str, dict[str, Any]] = {}
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.max_connections = max_connections
        self._message_handlers: dict[MessageType, Callable] = {}
        self._lock = asyncio.Lock()

    async def connect(self, node_id: str, websocket: WebSocket) -> bool:
        """
        Accept a new WebSocket connection.

        Returns:
            True if connection accepted, False if rejected
        """
        async with self._lock:
            if len(self.active_connections) >= self.max_connections:
                await websocket.close(code=1013, reason="Max connections reached")
                return False

            await websocket.accept()
            self.active_connections[node_id] = websocket
            self.connection_metadata[node_id] = {
                "connected_at": time.time(),
                "last_heartbeat": time.time(),
                "messages_received": 0,
                "messages_sent": 0,
            }

            return True

    def disconnect(self, node_id: str):
        """Remove a WebSocket connection."""
        self.active_connections.pop(node_id, None)
        self.connection_metadata.pop(node_id, None)

    async def send_message(self, node_id: str, message: WebSocketMessage) -> bool:
        """
        Send a message to a specific node.

        Returns:
            True if sent successfully, False otherwise
        """
        websocket = self.active_connections.get(node_id)
        if not websocket:
            return False

        try:
            await websocket.send_text(message.to_json())

            if node_id in self.connection_metadata:
                self.connection_metadata[node_id]["messages_sent"] += 1

            return True
        except Exception:
            self.disconnect(node_id)
            return False

    async def broadcast(self, message: WebSocketMessage, exclude: Optional[set[str]] = None):
        """Broadcast a message to all connected nodes."""
        exclude = exclude or set()

        disconnected = []
        for node_id, websocket in self.active_connections.items():
            if node_id in exclude:
                continue

            try:
                await websocket.send_text(message.to_json())
            except Exception:
                disconnected.append(node_id)

        for node_id in disconnected:
            self.disconnect(node_id)

    def register_handler(self, message_type: MessageType, handler: Callable):
        """Register a handler for a specific message type."""
        self._message_handlers[message_type] = handler

    async def handle_message(self, node_id: str, data: str) -> Optional[WebSocketMessage]:
        """
        Handle an incoming message from a node.

        Returns:
            Response message if any
        """
        try:
            message = WebSocketMessage.from_json(data)

            if node_id in self.connection_metadata:
                self.connection_metadata[node_id]["messages_received"] += 1
                self.connection_metadata[node_id]["last_heartbeat"] = time.time()

            if message.type == MessageType.HEARTBEAT:
                return WebSocketMessage(
                    type=MessageType.HEARTBEAT_ACK, payload={"server_time": time.time()}
                )

            if message.type == MessageType.PING:
                return WebSocketMessage(type=MessageType.PONG, payload={"server_time": time.time()})

            handler = self._message_handlers.get(message.type)
            if handler:
                return await handler(node_id, message)

            return None

        except json.JSONDecodeError:
            return WebSocketMessage(type=MessageType.ERROR, payload={"error": "Invalid JSON"})
        except Exception as e:
            return WebSocketMessage(type=MessageType.ERROR, payload={"error": str(e)})

    def get_connection_stats(self) -> dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": len(self.active_connections),
            "connections": {
                node_id: {
                    "connected_at": meta["connected_at"],
                    "last_heartbeat": meta["last_heartbeat"],
                    "messages_received": meta["messages_received"],
                    "messages_sent": meta["messages_sent"],
                }
                for node_id, meta in self.connection_metadata.items()
            },
        }

    async def check_timeouts(self) -> list[str]:
        """
        Check for timed-out connections.

        Returns:
            List of disconnected node IDs
        """
        current_time = time.time()
        timed_out = []

        for node_id, meta in self.connection_metadata.items():
            if current_time - meta["last_heartbeat"] > self.heartbeat_timeout:
                timed_out.append(node_id)

        for node_id in timed_out:
            self.disconnect(node_id)

        return timed_out


class NodeWebSocketClient:
    """
    WebSocket client for node-scheduler communication.

    Usage:
        client = NodeWebSocketClient(
            scheduler_url="ws://localhost:8000",
            node_id="node-001"
        )

        await client.connect()
        await client.send_heartbeat()

        async for message in client.listen():
            print(f"Received: {message}")
    """

    def __init__(
        self,
        scheduler_url: str,
        node_id: str,
        heartbeat_interval: int = 30,
        reconnect_delay: int = 5,
        max_reconnect_attempts: int = 10,
    ):
        self.scheduler_url = scheduler_url
        self.node_id = node_id
        self.heartbeat_interval = heartbeat_interval
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts
        self._ws = None
        self._connected = False
        self._reconnect_count = 0

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        """
        Connect to the scheduler WebSocket endpoint.

        Returns:
            True if connected successfully
        """
        try:
            import websockets

            ws_url = f"{self.scheduler_url}/ws/node/{self.node_id}"
            self._ws = await websockets.connect(ws_url)
            self._connected = True
            self._reconnect_count = 0
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Disconnect from the scheduler."""
        if self._ws:
            await self._ws.close()
            self._ws = None
        self._connected = False

    async def reconnect(self) -> bool:
        """Attempt to reconnect to the scheduler."""
        while self._reconnect_count < self.max_reconnect_attempts:
            self._reconnect_count += 1
            print(f"Reconnecting... (attempt {self._reconnect_count})")

            if await self.connect():
                return True

            await asyncio.sleep(self.reconnect_delay)

        return False

    async def send_message(self, message: WebSocketMessage) -> bool:
        """Send a message to the scheduler."""
        if not self._connected or not self._ws:
            return False

        try:
            await self._ws.send(message.to_json())
            return True
        except Exception:
            self._connected = False
            return False

    async def send_heartbeat(
        self,
        is_idle: bool = True,
        cpu_usage: float = 0.0,
        memory_usage: float = 0.0,
        available_resources: Optional[dict] = None,
    ) -> bool:
        """Send a heartbeat message to the scheduler."""
        message = WebSocketMessage(
            type=MessageType.HEARTBEAT,
            payload={
                "node_id": self.node_id,
                "is_idle": is_idle,
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
                "available_resources": available_resources or {},
                "timestamp": time.time(),
            },
        )
        return await self.send_message(message)

    async def send_task_result(
        self, task_id: int, result: Any, success: bool = True, error: Optional[str] = None
    ) -> bool:
        """Send task execution result to the scheduler."""
        message = WebSocketMessage(
            type=MessageType.TASK_RESULT,
            payload={
                "node_id": self.node_id,
                "task_id": task_id,
                "result": result,
                "success": success,
                "error": error,
                "timestamp": time.time(),
            },
        )
        return await self.send_message(message)

    async def receive_message(self) -> Optional[WebSocketMessage]:
        """Receive a message from the scheduler."""
        if not self._connected or not self._ws:
            return None

        try:
            data = await self._ws.recv()
            return WebSocketMessage.from_json(data)
        except Exception:
            self._connected = False
            return None

    async def listen(self):
        """Async generator for receiving messages."""
        while self._connected:
            message = await self.receive_message()
            if message:
                yield message
            else:
                if not await self.reconnect():
                    break

    async def heartbeat_loop(self):
        """Background task for sending periodic heartbeats."""
        while True:
            if self._connected:
                await self.send_heartbeat()
            await asyncio.sleep(self.heartbeat_interval)


def setup_websocket_routes(app, manager: ConnectionManager, storage):
    """
    Setup WebSocket routes for a FastAPI application.

    Usage:
        from fastapi import FastAPI
        from websocket_comm import ConnectionManager, setup_websocket_routes

        app = FastAPI()
        manager = ConnectionManager()
        setup_websocket_routes(app, manager, storage)
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI is required for WebSocket support")

    @app.websocket("/ws/node/{node_id}")
    async def websocket_node(websocket: WebSocket, node_id: str):
        connected = await manager.connect(node_id, websocket)
        if not connected:
            return

        try:
            while True:
                data = await websocket.receive_text()
                response = await manager.handle_message(node_id, data)

                if response:
                    await manager.send_message(node_id, response)

        except WebSocketDisconnect:
            manager.disconnect(node_id)

    async def handle_task_result(node_id: str, message: WebSocketMessage):
        payload = message.payload
        task_id = payload.get("task_id")
        result = payload.get("result")
        success = payload.get("success", True)
        error = payload.get("error")

        if success:
            await storage.update_task(
                task_id, {"status": "completed", "result": result, "completed_at": time.time()}
            )
        else:
            await storage.update_task(
                task_id, {"status": "failed", "error": error, "completed_at": time.time()}
            )

        return WebSocketMessage(
            type=MessageType.HEARTBEAT_ACK, payload={"received": True, "task_id": task_id}
        )

    manager.register_handler(MessageType.TASK_RESULT, handle_task_result)

    async def handle_heartbeat(node_id: str, message: WebSocketMessage):
        payload = message.payload

        await storage.update_node(
            node_id,
            {
                "last_heartbeat": time.time(),
                "is_idle": payload.get("is_idle", False),
                "cpu_usage": payload.get("cpu_usage", 0),
                "memory_usage": payload.get("memory_usage", 0),
                "available_resources": payload.get("available_resources", {}),
            },
        )

        pending_task = await storage.get_pending_task_for_node(node_id)
        if pending_task:
            return WebSocketMessage(
                type=MessageType.TASK_ASSIGNED,
                payload={
                    "task_id": pending_task.task_id,
                    "code": pending_task.code,
                    "timeout": pending_task.timeout,
                    "resources": pending_task.resources,
                },
            )

        return WebSocketMessage(
            type=MessageType.HEARTBEAT_ACK, payload={"server_time": time.time()}
        )

    manager.register_handler(MessageType.HEARTBEAT, handle_heartbeat)

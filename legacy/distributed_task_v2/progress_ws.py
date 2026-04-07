"""
Real-time Progress Monitoring via WebSocket.

Implements WebSocket-based progress tracking for distributed tasks,
providing real-time updates on task status, stage progress, and chunk completion.
"""

import asyncio
import hashlib
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
import contextlib


class MessageType(Enum):
    TASK_STATUS = "task_status"
    STAGE_PROGRESS = "stage_progress"
    CHUNK_COMPLETE = "chunk_complete"
    TASK_RESULT = "task_result"
    TASK_ERROR = "task_error"
    NODE_STATUS = "node_status"
    SYSTEM_STATS = "system_stats"


@dataclass
class ProgressUpdate:
    """Progress update message."""
    task_id: str
    message_type: MessageType
    timestamp: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "task_id": self.task_id,
            "message_type": self.message_type.value,
            "timestamp": self.timestamp,
            "data": self.data,
        })

    @classmethod
    def from_json(cls, data: str) -> "ProgressUpdate":
        obj = json.loads(data)
        return cls(
            task_id=obj["task_id"],
            message_type=MessageType(obj["message_type"]),
            timestamp=obj.get("timestamp", time.time()),
            data=obj.get("data", {}),
        )


@dataclass
class TaskProgress:
    """Task progress information."""
    task_id: str
    status: str
    progress: float
    total_stages: int = 0
    completed_stages: int = 0
    current_stage: Optional[str] = None
    started_at: Optional[float] = None
    estimated_completion: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "progress": self.progress,
            "total_stages": self.total_stages,
            "completed_stages": self.completed_stages,
            "current_stage": self.current_stage,
            "started_at": self.started_at,
            "estimated_completion": self.estimated_completion,
        }


@dataclass
class StageProgress:
    """Stage progress information."""
    stage_id: str
    task_id: str
    status: str
    progress: float
    total_chunks: int = 0
    completed_chunks: int = 0
    failed_chunks: int = 0
    started_at: Optional[float] = None
    estimated_completion: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "task_id": self.task_id,
            "status": self.status,
            "progress": self.progress,
            "total_chunks": self.total_chunks,
            "completed_chunks": self.completed_chunks,
            "failed_chunks": self.failed_chunks,
            "started_at": self.started_at,
            "estimated_completion": self.estimated_completion,
        }


class ProgressTracker:
    """Tracks progress of distributed tasks."""

    def __init__(self):
        self._task_progress: dict[str, TaskProgress] = {}
        self._stage_progress: dict[str, StageProgress] = {}
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._history: dict[str, list[ProgressUpdate]] = defaultdict(list)
        self._max_history = 100

    def register_task(self, task_id: str, total_stages: int) -> TaskProgress:
        """Register a new task for tracking."""
        progress = TaskProgress(
            task_id=task_id,
            status="pending",
            progress=0.0,
            total_stages=total_stages,
            completed_stages=0,
            started_at=time.time(),
        )
        self._task_progress[task_id] = progress
        self._notify(ProgressUpdate(
            task_id=task_id,
            message_type=MessageType.TASK_STATUS,
            data=progress.to_dict(),
        ))
        return progress

    def register_stage(
        self,
        task_id: str,
        stage_id: str,
        total_chunks: int
    ) -> StageProgress:
        """Register a new stage for tracking."""
        progress = StageProgress(
            stage_id=stage_id,
            task_id=task_id,
            status="pending",
            progress=0.0,
            total_chunks=total_chunks,
            completed_chunks=0,
            failed_chunks=0,
            started_at=time.time(),
        )
        self._stage_progress[f"{task_id}:{stage_id}"] = progress
        self._notify(ProgressUpdate(
            task_id=task_id,
            message_type=MessageType.STAGE_PROGRESS,
            data=progress.to_dict(),
        ))
        return progress

    def update_task_status(self, task_id: str, status: str, progress: float = None):
        """Update task status."""
        if task_id not in self._task_progress:
            return

        task = self._task_progress[task_id]
        task.status = status
        if progress is not None:
            task.progress = progress

        self._notify(ProgressUpdate(
            task_id=task_id,
            message_type=MessageType.TASK_STATUS,
            data=task.to_dict(),
        ))

    def update_stage_progress(
        self,
        task_id: str,
        stage_id: str,
        completed_chunks: int = None,
        failed_chunks: int = None,
        status: str = None
    ):
        """Update stage progress."""
        key = f"{task_id}:{stage_id}"
        if key not in self._stage_progress:
            return

        stage = self._stage_progress[key]
        if completed_chunks is not None:
            stage.completed_chunks = completed_chunks
        if failed_chunks is not None:
            stage.failed_chunks = failed_chunks
        if status is not None:
            stage.status = status

        if stage.total_chunks > 0:
            stage.progress = stage.completed_chunks / stage.total_chunks

        self._notify(ProgressUpdate(
            task_id=task_id,
            message_type=MessageType.STAGE_PROGRESS,
            data=stage.to_dict(),
        ))

    def complete_chunk(self, task_id: str, stage_id: str, chunk_id: str, result: Any = None):
        """Mark a chunk as completed."""
        key = f"{task_id}:{stage_id}"
        if key not in self._stage_progress:
            return

        stage = self._stage_progress[key]
        # 第一个chunk完成时将状态设为running
        if stage.status == "pending":
            stage.status = "running"
        stage.completed_chunks += 1
        if stage.total_chunks > 0:
            stage.progress = stage.completed_chunks / stage.total_chunks

        self._notify(ProgressUpdate(
            task_id=task_id,
            message_type=MessageType.CHUNK_COMPLETE,
            data={
                "chunk_id": chunk_id,
                "stage_id": stage_id,
                "result": result,
                "stage_progress": stage.to_dict(),
            },
        ))

        self._update_task_from_stages(task_id)

    def fail_chunk(self, task_id: str, stage_id: str, chunk_id: str, error: str):
        """Mark a chunk as failed."""
        key = f"{task_id}:{stage_id}"
        if key not in self._stage_progress:
            return

        stage = self._stage_progress[key]
        stage.failed_chunks += 1

        self._notify(ProgressUpdate(
            task_id=task_id,
            message_type=MessageType.TASK_ERROR,
            data={
                "chunk_id": chunk_id,
                "stage_id": stage_id,
                "error": error,
                "stage_progress": stage.to_dict(),
            },
        ))

    def complete_task(self, task_id: str, result: Any = None):
        """Mark a task as completed."""
        if task_id not in self._task_progress:
            return

        task = self._task_progress[task_id]
        task.status = "completed"
        task.progress = 1.0

        self._notify(ProgressUpdate(
            task_id=task_id,
            message_type=MessageType.TASK_RESULT,
            data={
                "status": "completed",
                "result": result,
                "task_progress": task.to_dict(),
            },
        ))

    def _update_task_from_stages(self, task_id: str):
        """Update task progress from stage progress."""
        if task_id not in self._task_progress:
            return

        task = self._task_progress[task_id]
        stage_keys = [k for k in self._stage_progress if k.startswith(f"{task_id}:")]

        if not stage_keys:
            return

        total_progress = sum(
            self._stage_progress[k].progress
            for k in stage_keys
        )
        task.progress = total_progress / len(stage_keys)
        task.completed_stages = sum(
            1 for k in stage_keys
            if self._stage_progress[k].status == "completed"
        )

    def subscribe(self, task_id: str, callback: Callable):
        """Subscribe to progress updates for a task."""
        self._subscribers[task_id].append(callback)

    def unsubscribe(self, task_id: str, callback: Callable):
        """Unsubscribe from progress updates."""
        if task_id in self._subscribers:
            with contextlib.suppress(ValueError):
                self._subscribers[task_id].remove(callback)

    def _notify(self, update: ProgressUpdate):
        """Notify subscribers of an update."""
        self._history[update.task_id].append(update)
        if len(self._history[update.task_id]) > self._max_history:
            self._history[update.task_id].pop(0)

        for callback in self._subscribers.get(update.task_id, []):
            with contextlib.suppress(Exception):
                callback(update)

    def get_task_progress(self, task_id: str) -> Optional[TaskProgress]:
        """Get task progress."""
        return self._task_progress.get(task_id)

    def get_stage_progress(self, task_id: str, stage_id: str) -> Optional[StageProgress]:
        """Get stage progress."""
        return self._stage_progress.get(f"{task_id}:{stage_id}")

    def get_history(self, task_id: str, limit: int = 10) -> list[ProgressUpdate]:
        """Get progress history for a task."""
        history = self._history.get(task_id, [])
        return history[-limit:]


class WebSocketProgressServer:
    """WebSocket server for real-time progress updates."""

    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.tracker = ProgressTracker()
        self._running = False
        self._server: Optional[asyncio.Server] = None
        self._clients: dict[str, asyncio.StreamWriter] = {}

    async def start(self):
        """Start the WebSocket server."""
        if self._running:
            return

        self._running = True
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        print(f"[Progress WS] Server started on {self.host}:{self.port}")

    async def stop(self):
        """Stop the WebSocket server."""
        if not self._running:
            return

        self._running = False

        for writer in self._clients.values():
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a WebSocket client connection."""
        client_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        self._clients[client_id] = writer

        try:
            async for message in self._read_messages(reader):
                if message:
                    await self._handle_message(message, writer)
        except Exception as e:
            print(f"[Progress WS] Client error: {e}")
        finally:
            if client_id in self._clients:
                del self._clients[client_id]

    async def _read_messages(self, reader: asyncio.StreamReader):
        """Read WebSocket messages."""
        while self._running:
            try:
                header = await reader.read(2)
                if not header:
                    break

                length = int.from_bytes(header, "big")
                mask = await reader.read(4)
                if mask != b"\x00\xff\xff":
                    break

                payload = await reader.read(length)
                yield payload
            except asyncio.IncompleteReadError:
                break

    async def _handle_message(self, message: bytes, writer: asyncio.StreamWriter):
        """Handle a WebSocket message."""
        try:
            data = json.loads(message.decode())
            action = data.get("action")

            if action == "subscribe":
                task_id = data.get("task_id")
                if task_id:
                    self.tracker.subscribe(task_id, lambda update: self._send_update(writer, update))
            elif action == "get_progress":
                task_id = data.get("task_id")
                if task_id:
                    progress = self.tracker.get_task_progress(task_id)
                    if progress:
                        await self._send_response(writer, {
                            "action": "progress",
                            "data": progress.to_dict(),
                        })
        except Exception as e:
            print(f"[Progress WS] Message handling error: {e}")

    async def _send_update(self, writer: asyncio.StreamWriter, update: ProgressUpdate):
        """Send a progress update to a client."""
        message = update.to_json()
        frame = self._create_frame(message)
        writer.write(frame)
        await writer.drain()

    async def _send_response(self, writer: asyncio.StreamWriter, data: dict):
        """Send a response to a client."""
        message = json.dumps(data)
        frame = self._create_frame(message)
        writer.write(frame)
        await writer.drain()

    def _create_frame(self, message: str) -> bytes:
        """Create a WebSocket frame."""
        length = len(message)
        return length.to_bytes(2, "big") + b"\x00\xff\xff" + message.encode()


__all__ = [
    "MessageType",
    "ProgressUpdate",
    "TaskProgress",
    "StageProgress",
    "ProgressTracker",
    "WebSocketProgressServer",
]

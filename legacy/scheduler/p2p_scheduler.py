"""
P2P Scheduler - HTTP API Gateway for P2P Computing Network.

This scheduler provides:
- HTTP API for task submission (compatible with simple_server.py)
- P2P task broadcasting to worker nodes
- Result collection from P2P network
- Web dashboard for monitoring

Usage:
    # Start the P2P scheduler
    python -m legacy.scheduler.p2p_scheduler --port 8000 --p2p-port 8765

    # Submit a task via HTTP
    curl -X POST http://localhost:8000/submit -H "Content-Type: application/json" \
         -d '{"code": "print(1+1)"}'
"""

import argparse
import asyncio
import hashlib
import os
import sys
import time
import uuid
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import BackgroundTasks, Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from legacy.node.p2p_client import P2PClient, Task, TaskResult


class TaskSubmission(BaseModel):
    code: str
    timeout: Optional[int] = 300
    resources: Optional[dict[str, Any]] = {"cpu": 1.0, "memory": 512}
    user_id: Optional[str] = None


class TaskInfo(BaseModel):
    task_id: str
    code: str
    status: str
    created_at: float
    assigned_node: Optional[str] = None
    result: Optional[str] = None
    completed_at: Optional[float] = None


class P2PScheduler:
    """P2P Scheduler that bridges HTTP API with P2P network."""

    def __init__(self, http_port: int = 8000, p2p_port: int = 8765):
        self.http_port = http_port
        self.p2p_port = p2p_port

        self.node_id = hashlib.sha256(
            f"scheduler-{time.time()}-{uuid.uuid4()}".encode()
        ).hexdigest()[:16]

        self.p2p_client: Optional[P2PClient] = None
        self._running = False

        self._tasks: dict[str, Task] = {}
        self._results: dict[str, TaskResult] = {}
        self._stats = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "start_time": time.time(),
        }

    async def start(self):
        self.p2p_client = P2PClient(
            node_id=f"scheduler-{self.node_id}",
            port=self.p2p_port,
            is_bootstrap=True,
            scheduler_mode=True,
        )

        self.p2p_client.capabilities["is_scheduler"] = True

        success = await self.p2p_client.start()
        if not success:
            raise RuntimeError("Failed to start P2P client")

        self._running = True
        print(f"[P2P Scheduler] Started on HTTP port {self.http_port}, P2P port {self.p2p_port}")

    async def stop(self):
        self._running = False
        if self.p2p_client:
            await self.p2p_client.stop()

    async def submit_task(self, submission: TaskSubmission) -> str:
        task_id = hashlib.sha256(
            f"{submission.code}{time.time()}{uuid.uuid4()}".encode()
        ).hexdigest()[:16]

        task = Task(
            task_id=task_id,
            code=submission.code,
            timeout=submission.timeout or 300,
            required_resources=submission.resources or {"cpu": 1.0, "memory": 512},
        )

        self._tasks[task_id] = task
        self._stats["tasks_submitted"] += 1

        if self.p2p_client:
            self.p2p_client._task_queue.append(task)
            self.p2p_client._pending_tasks[task_id] = task

            await self.p2p_client.broadcast(
                "task_broadcast",
                {
                    "task_id": task_id,
                    "code": submission.code,
                    "timeout": task.timeout,
                    "required_resources": task.required_resources,
                    "sender_id": self.node_id,
                },
            )

        print(f"[P2P Scheduler] Task {task_id} submitted and broadcast")
        return task_id

    async def get_task_status(self, task_id: str) -> Optional[dict]:
        if task_id not in self._tasks:
            return None

        task = self._tasks[task_id]
        result = self._results.get(task_id)

        return {
            "task_id": task.task_id,
            "status": task.status,
            "code": task.code[:100] + "..." if len(task.code) > 100 else task.code,
            "created_at": task.created_at,
            "assigned_node": task.assigned_node,
            "result": result.result if result else None,
            "execution_time": result.execution_time if result else None,
            "completed_at": task.completed_at,
            "success": result.success if result else None,
        }

    async def get_task_result(self, task_id: str, timeout: float = 60.0) -> Optional[TaskResult]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            if task_id in self._results:
                return self._results[task_id]
            await asyncio.sleep(0.5)
        return None

    def get_all_results(self) -> list[dict]:
        return [
            {
                "task_id": task_id,
                "node_id": result.node_id,
                "result": result.result[:500] if len(result.result) > 500 else result.result,
                "execution_time": result.execution_time,
                "success": result.success,
            }
            for task_id, result in self._results.items()
        ]

    def get_stats(self) -> dict:
        p2p_stats = self.p2p_client.get_stats() if self.p2p_client else {}

        return {
            "scheduler": {
                "tasks_submitted": self._stats["tasks_submitted"],
                "tasks_completed": self._stats["tasks_completed"],
                "tasks_failed": self._stats["tasks_failed"],
                "uptime": time.time() - self._stats["start_time"],
            },
            "p2p": p2p_stats,
            "queue": {
                "pending": len(self._tasks) - len(self._results),
                "completed": len(self._results),
            },
        }

    def get_nodes(self) -> list[dict]:
        if not self.p2p_client:
            return []

        nodes = []
        for peer in self.p2p_client.dht.get_all_peers():
            nodes.append(
                {
                    "node_id": peer.node_id,
                    "ip": peer.ip,
                    "port": peer.port,
                    "state": peer.state.value,
                    "last_seen": peer.last_seen,
                    "capabilities": peer.capabilities,
                }
            )

        return nodes


scheduler: Optional[P2PScheduler] = None

app = FastAPI(
    title="P2P Computing Scheduler",
    description="Distributed task scheduler using P2P network",
    version="1.0.0",
)

_cors_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:8000")
_cors_origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in _cors_origins else _cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    global scheduler
    print("=" * 60)
    print("P2P Computing Scheduler v1.0.0")
    print("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    global scheduler
    if scheduler:
        await scheduler.stop()


@app.get("/")
async def root():
    return {
        "service": "P2P Computing Scheduler",
        "status": "running",
        "version": "1.0.0",
        "scheduler": scheduler.get_stats() if scheduler else None,
    }


@app.get("/health")
async def health_check():
    stats = scheduler.get_stats() if scheduler else {}
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "p2p_peers": stats.get("p2p", {}).get("peers", 0),
    }


@app.post("/submit")
async def submit_task(submission: TaskSubmission, background_tasks: BackgroundTasks):
    if not submission.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty")

    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    task_id = await scheduler.submit_task(submission)

    return {
        "task_id": task_id,
        "status": "submitted",
        "message": f"Task {task_id} has been broadcast to P2P network",
    }


@app.get("/get_task")
async def get_task(node_id: Optional[str] = None):
    if not scheduler or not scheduler.p2p_client:
        return {"task_id": None, "code": None, "status": "no_scheduler"}

    if scheduler.p2p_client._task_queue:
        task = scheduler.p2p_client._task_queue.pop(0)
        task.status = "assigned"
        task.assigned_node = node_id

        return {
            "task_id": task.task_id,
            "code": task.code,
            "status": "assigned",
            "assigned_node": node_id,
        }

    return {"task_id": None, "code": None, "status": "no_tasks"}


@app.post("/submit_result")
async def submit_result(
    task_id: str = Body(...),
    result: str = Body(...),
    node_id: Optional[str] = Body(None),
):
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    if task_id not in scheduler._tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = scheduler._tasks[task_id]
    task.status = "completed"
    task.result = result
    task.completed_at = time.time()

    task_result = TaskResult(
        task_id=task_id,
        node_id=node_id or "unknown",
        result=result,
        execution_time=task.completed_at - task.created_at,
        success=True,
    )

    scheduler._results[task_id] = task_result
    scheduler._stats["tasks_completed"] += 1

    return {"success": True, "task_id": task_id}


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    status = await scheduler.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")

    return status


@app.get("/results")
async def get_results():
    if not scheduler:
        return {"count": 0, "results": []}

    results = scheduler.get_all_results()
    return {"count": len(results), "results": results}


@app.get("/stats")
async def get_stats():
    if not scheduler:
        return {"error": "Scheduler not initialized"}

    return scheduler.get_stats()


@app.get("/api/nodes")
async def list_nodes(online_only: bool = True):
    if not scheduler:
        return {"count": 0, "nodes": []}

    nodes = scheduler.get_nodes()

    if online_only:
        nodes = [n for n in nodes if n["state"] == "online"]

    return {"count": len(nodes), "nodes": nodes}


@app.post("/api/nodes/register")
async def register_node(node_id: str = Body(...), capacity: dict = Body(default={})):
    return {
        "status": "registered",
        "node_id": node_id,
        "message": "P2P nodes register automatically via DHT",
    }


@app.post("/api/nodes/{node_id}/heartbeat")
async def update_heartbeat(node_id: str):
    return {"status": "acknowledged", "node_id": node_id}


async def run_server(http_port: int, p2p_port: int):
    global scheduler

    import uvicorn

    scheduler = P2PScheduler(http_port=http_port, p2p_port=p2p_port)
    await scheduler.start()

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=http_port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    try:
        await server.serve()
    finally:
        await scheduler.stop()


def main():
    parser = argparse.ArgumentParser(description="P2P Computing Scheduler")
    parser.add_argument("--port", type=int, default=8000, help="HTTP API port")
    parser.add_argument("--p2p-port", type=int, default=8765, help="P2P network port")

    args = parser.parse_args()

    print("=" * 60)
    print("P2P Computing Scheduler")
    print("=" * 60)
    print(f"HTTP API Port: {args.port}")
    print(f"P2P Network Port: {args.p2p_port}")
    print("=" * 60)

    asyncio.run(run_server(args.port, args.p2p_port))


if __name__ == "__main__":
    main()

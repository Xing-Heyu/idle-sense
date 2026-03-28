"""
Redis任务仓储实现

提供基于Redis的任务持久化存储
"""

import json
from datetime import datetime
from typing import Optional

from src.core.entities import Task, TaskStatus, TaskType
from src.core.interfaces.repositories import ITaskRepository


class RedisTaskRepository(ITaskRepository):
    """
    基于Redis的任务仓储实现

    提供任务数据的持久化存储，支持：
    - 分布式访问
    - 高性能读写
    - TTL自动过期
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "idle_sense:task:",
        ttl: int = 86400
    ):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.ttl = ttl
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                import redis.asyncio as redis
                self._client = redis.from_url(self.redis_url)
            except ImportError as e:
                raise ImportError(
                    "Redis storage requires the redis package. "
                    "Install it with: pip install redis"
                ) from e
        return self._client

    def _task_to_dict(self, task: Task) -> str:
        return json.dumps({
            "task_id": task.task_id,
            "code": task.code,
            "status": task.status.value,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "user_id": task.user_id,
            "timeout": task.timeout,
            "cpu_request": task.cpu_request,
            "memory_request": task.memory_request,
            "task_type": task.task_type.value,
            "assigned_node": task.assigned_node,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "result": task.result,
            "error": task.error,
            "resources": task.resources
        })

    def _dict_to_task(self, data: str) -> Task:
        obj = json.loads(data)
        return Task(
            task_id=obj["task_id"],
            code=obj["code"],
            status=TaskStatus(obj["status"]),
            created_at=datetime.fromisoformat(obj["created_at"]) if obj.get("created_at") else datetime.now(),
            user_id=obj.get("user_id"),
            timeout=obj.get("timeout", 300),
            cpu_request=obj.get("cpu_request", 1.0),
            memory_request=obj.get("memory_request", 512),
            task_type=TaskType(obj["task_type"]) if obj.get("task_type") else TaskType.SINGLE_NODE,
            assigned_node=obj.get("assigned_node"),
            started_at=datetime.fromisoformat(obj["started_at"]) if obj.get("started_at") else None,
            completed_at=datetime.fromisoformat(obj["completed_at"]) if obj.get("completed_at") else None,
            result=obj.get("result"),
            error=obj.get("error"),
            resources=obj.get("resources", {})
        )

    async def get_by_id(self, task_id: str) -> Optional[Task]:
        client = await self._get_client()
        key = f"{self.key_prefix}{task_id}"
        data = await client.get(key)
        return self._dict_to_task(data.decode()) if data else None

    async def save(self, task: Task) -> Task:
        client = await self._get_client()
        key = f"{self.key_prefix}{task.task_id}"
        await client.setex(key, self.ttl, self._task_to_dict(task))
        await client.sadd(f"{self.key_prefix}all", task.task_id)
        await client.sadd(f"{self.key_prefix}status:{task.status.value}", task.task_id)
        if task.user_id:
            await client.sadd(f"{self.key_prefix}user:{task.user_id}", task.task_id)
        return task

    async def update(self, task: Task) -> Task:
        client = await self._get_client()
        old_task = await self.get_by_id(task.task_id)
        if old_task:
            if old_task.status != task.status:
                await client.srem(f"{self.key_prefix}status:{old_task.status.value}", task.task_id)
            if old_task.user_id and old_task.user_id != task.user_id:
                await client.srem(f"{self.key_prefix}user:{old_task.user_id}", task.task_id)
        return await self.save(task)

    async def delete(self, task_id: str) -> bool:
        client = await self._get_client()
        task = await self.get_by_id(task_id)
        if task:
            await client.delete(f"{self.key_prefix}{task_id}")
            await client.srem(f"{self.key_prefix}all", task_id)
            await client.srem(f"{self.key_prefix}status:{task.status.value}", task_id)
            if task.user_id:
                await client.srem(f"{self.key_prefix}user:{task.user_id}", task_id)
            return True
        return False

    async def list_by_user(self, user_id: str, limit: int = 100) -> list[Task]:
        client = await self._get_client()
        task_ids = await client.smembers(f"{self.key_prefix}user:{user_id}")
        tasks = []
        for task_id in task_ids[:limit]:
            task = await self.get_by_id(task_id.decode())
            if task:
                tasks.append(task)
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)[:limit]

    async def list_by_status(self, status: TaskStatus, limit: int = 100) -> list[Task]:
        client = await self._get_client()
        task_ids = await client.smembers(f"{self.key_prefix}status:{status.value}")
        tasks = []
        for task_id in task_ids[:limit]:
            task = await self.get_by_id(task_id.decode())
            if task:
                tasks.append(task)
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)[:limit]

    async def list_all(self, limit: int = 100) -> list[Task]:
        client = await self._get_client()
        task_ids = await client.smembers(f"{self.key_prefix}all")
        tasks = []
        for task_id in task_ids[:limit]:
            task = await self.get_by_id(task_id.decode())
            if task:
                tasks.append(task)
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)[:limit]

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None


__all__ = ["RedisTaskRepository"]

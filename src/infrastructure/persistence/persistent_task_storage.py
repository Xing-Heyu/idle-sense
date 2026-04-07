import asyncio
import concurrent.futures
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from src.core.entities.task import Task, TaskStatus
from src.infrastructure.persistence import ensure_data_dirs, get_db_path
from src.infrastructure.repositories.sqlite_task_repository import SQLiteTaskRepository
import contextlib


@dataclass
class CachedTaskInfo:
    """缓存任务信息，兼容调度器 TaskInfo 结构"""
    task_id: int
    code: str
    status: str
    created_at: float
    assigned_at: Optional[float] = None
    assigned_node: Optional[str] = None
    completed_at: Optional[float] = None
    result: Optional[str] = None
    required_resources: dict[str, Any] = field(default_factory=lambda: {"cpu": 1.0, "memory": 512})
    user_id: Optional[str] = None
    _internal_task_id: Optional[str] = None


class PersistentTaskStorage:
    """
    持久化任务存储模块

    包装 SQLiteTaskRepository 并添加内存缓存层，提供与 OptimizedMemoryStorage 兼容的同步接口。

    架构：
        调度器调用 (sync)  -->  PersistentTaskStorage  -->  内存缓存 (dict)
                                                        -->  SQLiteTaskRepository (async)

    特性：
        - 内存缓存加速读取，写穿透到 SQLite
        - 自动连接重连机制
        - 异步初始化 + 同步便捷方法
        - 批量操作支持
        - int task_id（调度器兼容）<--> str task_id（SQLite）双向映射
    """

    def __init__(self, db_path=None):
        self._db_path = str(db_path or get_db_path())
        self._repo: Optional[SQLiteTaskRepository] = None
        self._initialized = False
        self._lock = threading.RLock()

        self._task_id_counter = 1
        self._id_map: dict[int, str] = {}
        self._reverse_id_map: dict[str, int] = {}

        self._cache: dict[int, CachedTaskInfo] = {}
        self._pending_tasks: list[int] = []
        self._assigned_tasks: dict[str, list[int]] = {}

        self._stats = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "reconnect_count": 0,
            "last_cleanup": time.time(),
        }

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._executor_lock = threading.Lock()

    async def async_init(self) -> "PersistentTaskStorage":
        """异步初始化：创建数据目录、连接数据库、恢复已有任务"""
        ensure_data_dirs()
        self._repo = SQLiteTaskRepository(db_path=self._db_path)

        await self._recover_existing_tasks()

        self._initialized = True
        return self

    def init_sync(self) -> "PersistentTaskStorage":
        """同步便捷初始化方法"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, self.async_init())
                return future.result()
        else:
            return asyncio.run(self.async_init())

    def _ensure_init(self):
        """确保已初始化，未初始化则自动调用同步初始化"""
        if not self._initialized:
            self.init_sync()

    async def _recover_existing_tasks(self):
        """从数据库恢复已有任务到内存缓存，重建 ID 映射"""
        all_tasks = await self._repo.list_all(limit=10000)
        max_int_id = 0

        for task in all_tasks:
            int_id = self._task_id_counter
            try:
                resources = json.loads(json.dumps(task.resources)) if task.resources else {"cpu": 1.0, "memory": 512}
            except Exception:
                resources = {"cpu": 1.0, "memory": 512}

            cached = CachedTaskInfo(
                task_id=int_id,
                code=task.code or "",
                status=task.status.value if isinstance(task.status, TaskStatus) else str(task.status),
                created_at=task.created_at.timestamp() if task.created_at else time.time(),
                assigned_at=task.started_at.timestamp() if task.started_at else None,
                assigned_node=task.assigned_node,
                completed_at=task.completed_at.timestamp() if task.completed_at else None,
                result=task.result,
                required_resources=resources,
                user_id=task.user_id,
                _internal_task_id=task.task_id,
            )

            self._id_map[int_id] = task.task_id
            self._reverse_id_map[task.task_id] = int_id
            self._cache[int_id] = cached

            status_str = cached.status
            if status_str == "pending":
                self._pending_tasks.append(int_id)
            elif status_str in ("assigned", "running") and task.assigned_node:
                self._assigned_tasks.setdefault(task.assigned_node, []).append(int_id)

            max_int_id = max(max_int_id, int_id)
            self._task_id_counter = max_int_id + 1

    def _run_async(self, coro):
        """在专用线程中运行异步协程，带重连机制，兼容同步/异步调用上下文"""
        self._ensure_init()

        def _run_in_thread(c):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(c)
            finally:
                loop.close()

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with self._executor_lock:
                    if self._executor is None:
                        self._executor = concurrent.futures.ThreadPoolExecutor(
                            max_workers=1, thread_name_prefix="persistent_storage"
                        )
                    future = self._executor.submit(_run_in_thread, coro)
                return future.result(timeout=30)
            except Exception as e:
                if attempt < max_retries - 1:
                    self._stats["reconnect_count"] += 1
                    if self._repo and self._repo._conn:
                        try:
                            with self._executor_lock:
                                if self._executor:
                                    close_future = self._executor.submit(
                                        _run_in_thread, self._repo.close()
                                    )
                                    close_future.result(timeout=10)
                        except Exception:
                            pass
                        self._repo._conn = None
                    time.sleep(0.1 * (attempt + 1))
                else:
                    raise

    def _invalidate_cache(self, int_id: int):
        """使指定任务的缓存失效"""
        self._cache.pop(int_id, None)

    def _update_cache(self, int_id: int, cached: CachedTaskInfo):
        """更新内存缓存"""
        self._cache[int_id] = cached

    def add_task(self, code: str, timeout: int = 300, resources: Optional[dict] = None, user_id: Optional[str] = None) -> int:
        """添加新任务，返回 int 类型 task_id（兼容调度器接口）"""
        with self._lock:
            int_id = self._task_id_counter
            self._task_id_counter += 1

            res = resources or {"cpu": 1.0, "memory": 512}
            cpu_val = res.get("cpu", 1.0)
            mem_val = res.get("memory", 512)

            task = Task(
                code=code,
                user_id=user_id,
                timeout=timeout,
                cpu_request=float(cpu_val),
                memory_request=int(mem_val),
                resources=res.copy(),
            )

            saved = self._run_async(self._do_save_task(task, int_id))

            cached = CachedTaskInfo(
                task_id=int_id,
                code=code,
                status="pending",
                created_at=time.time(),
                required_resources=res.copy(),
                user_id=user_id,
                _internal_task_id=saved.task_id if saved else task.task_id,
            )
            self._update_cache(int_id, cached)
            self._pending_tasks.append(int_id)

            return int_id

    async def _do_save_task(self, task: Task, int_id: int) -> Task:
        """内部异步保存任务"""
        saved = await self._repo.save(task)
        self._id_map[int_id] = saved.task_id
        self._reverse_id_map[saved.task_id] = int_id
        return saved

    def get_task_for_node(self, node_id: str) -> Optional[CachedTaskInfo]:
        """为指定节点获取一个待处理任务（兼容调度器接口）"""
        with self._lock:
            node_cached = self._cache.values()
            best_task = None
            best_score = -1.0

            for tid in list(self._pending_tasks):
                cached = self._cache.get(tid)
                if not cached or cached.status != "pending":
                    continue

                req = cached.required_resources or {}
                score = 1.0
                if "cpu" in req:
                    score *= min(1.0, 4.0 / max(0.1, req.get("cpu", 1.0)))
                if "memory" in req:
                    score *= min(1.0, 8192 / max(1, req.get("memory", 512)))

                if score > best_score:
                    best_score = score
                    best_task = cached

            if best_task:
                best_task.status = "assigned"
                best_task.assigned_node = node_id
                best_task.assigned_at = time.time()
                self._pending_tasks.remove(best_task.task_id)
                self._assigned_tasks.setdefault(node_id, []).append(best_task.task_id)

                internal_id = self._id_map.get(best_task.task_id)
                if internal_id:
                    self._run_async(self._do_update_task_status(internal_id, "assigned", node_id))

                self._stats["tasks_processed"] += 1

            return best_task

    async def _do_update_task_status(self, internal_id: str, status: str, node_id: Optional[str] = None):
        """内部异步更新任务状态"""
        task = await self._repo.get_by_id(internal_id)
        if not task:
            return
        if status == "assigned":
            task.status = TaskStatus.RUNNING
            task.assigned_node = node_id
            task.started_at = datetime.now()
        elif status == "completed":
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
        elif status == "failed":
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
        await self._repo.save(task)

    def complete_task(self, task_id: int, result: str, node_id: Optional[str] = None) -> bool:
        """完成任务（兼容调度器接口）"""
        with self._lock:
            cached = self._cache.get(task_id)
            if not cached:
                return False

            if cached.status not in ("pending", "assigned", "running"):
                return False

            cached.status = "completed"
            cached.completed_at = time.time()
            cached.result = result

            actual_node = node_id or cached.assigned_node
            if actual_node and actual_node in self._assigned_tasks:
                tasks_list = self._assigned_tasks[actual_node]
                if task_id in tasks_list:
                    tasks_list.remove(task_id)

            internal_id = self._id_map.get(task_id)
            if internal_id:
                with contextlib.suppress(Exception):
                    self._run_async(self._do_complete_task(internal_id, result))

            return True

    async def _do_complete_task(self, internal_id: str, result: str):
        """内部异步完成任务"""
        task = await self._repo.get_by_id(internal_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            await self._repo.save(task)

    def get_task_status(self, task_id: int) -> Optional[dict[str, Any]]:
        """获取任务状态（兼容调度器接口）"""
        cached = self._cache.get(task_id)
        if not cached:
            internal_id = self._id_map.get(task_id)
            if internal_id:
                try:
                    task = self._run_async(self._repo.get_by_id(internal_id))
                    if task:
                        return self._task_to_status_dict(task, task_id)
                except Exception:
                    pass
            self._stats["cache_misses"] += 1
            return None

        self._stats["cache_hits"] += 1
        return {
            "task_id": cached.task_id,
            "status": cached.status,
            "result": cached.result,
            "created_at": cached.created_at,
            "assigned_at": cached.assigned_at,
            "assigned_node": cached.assigned_node,
            "completed_at": cached.completed_at,
            "required_resources": cached.required_resources,
            "user_id": cached.user_id,
        }

    def _task_to_status_dict(self, task: Task, int_id: int) -> dict[str, Any]:
        """将 Task 实体转换为状态字典"""
        return {
            "task_id": int_id,
            "status": task.status.value if isinstance(task.status, TaskStatus) else str(task.status),
            "result": task.result,
            "created_at": task.created_at.timestamp() if task.created_at else time.time(),
            "assigned_at": task.started_at.timestamp() if task.started_at else None,
            "assigned_node": task.assigned_node,
            "completed_at": task.completed_at.timestamp() if task.completed_at else None,
            "required_resources": task.resources or {},
            "user_id": task.user_id,
        }

    def get_all_results(self) -> list[dict[str, Any]]:
        """获取所有已完成任务的结果（兼容调度器接口）"""
        with self._lock:
            results = []
            for cached in self._cache.values():
                if cached.status == "completed":
                    results.append({
                        "task_id": cached.task_id,
                        "result": cached.result,
                        "completed_at": cached.completed_at,
                        "assigned_node": cached.assigned_node,
                        "user_id": cached.user_id,
                    })
            return results

    def get_system_stats(self) -> dict[str, Any]:
        """获取系统统计信息（兼容调度器接口）"""
        with self._lock:
            total = len(self._cache)
            completed = sum(1 for c in self._cache.values() if c.status == "completed")
            pending = len(self._pending_tasks)
            assigned = sum(len(tasks) for tasks in self._assigned_tasks.values())

            return {
                "tasks": {
                    "total": total,
                    "completed": completed,
                    "pending": pending,
                    "assigned": assigned,
                    "failed": total - completed - pending - assigned,
                },
                "nodes": {
                    "total": len(self._assigned_tasks),
                    "online": len(self._assigned_tasks),
                    "available": sum(1 for n in self._assigned_tasks if self._assigned_tasks[n]),
                    "offline": 0,
                },
                "scheduler": {**self._stats},
                "persistence": {
                    "db_path": self._db_path,
                    "initialized": self._initialized,
                    "cached_tasks": total,
                    "cache_hit_rate": (
                        round(self._stats["cache_hits"] / max(1, self._stats["cache_hits"] + self._stats["cache_misses"]), 4)
                    ),
                },
            }

    def batch_save(self, tasks: list[dict]) -> list[int]:
        """
        批量保存任务

        Args:
            tasks: 任务字典列表，每个字典包含 code, timeout, resources, user_id 等字段

        Returns:
            成功保存的 task_id 列表（int 类型）
        """
        ids = []
        for task_data in tasks:
            try:
                tid = self.add_task(
                    code=task_data.get("code", ""),
                    timeout=task_data.get("timeout", 300),
                    resources=task_data.get("resources"),
                    user_id=task_data.get("user_id"),
                )
                ids.append(tid)
            except Exception:
                self._stats["tasks_failed"] += 1
        return ids

    def batch_get(self, task_ids: list[int]) -> list[Optional[dict[str, Any]]]:
        """
        批量获取任务状态

        Args:
            task_ids: 任务 ID 列表（int 类型）

        Returns:
            任务状态字典列表，未找到的位置为 None
        """
        results = []
        for tid in task_ids:
            status = self.get_task_status(tid)
            results.append(status)
        return results

    def delete_task(self, task_id: int) -> dict[str, Any]:
        """删除任务"""
        with self._lock:
            cached = self._cache.get(task_id)
            if not cached:
                return {"success": False, "error": "任务不存在"}

            if cached.status not in ("pending", "assigned"):
                return {"success": False, "error": f"只能删除 pending 或 assigned 状态的任务，当前状态: {cached.status}"}

            if cached.status == "pending" and task_id in self._pending_tasks:
                self._pending_tasks.remove(task_id)
            elif cached.status == "assigned" and cached.assigned_node:
                node_tasks = self._assigned_tasks.get(cached.assigned_node, [])
                if task_id in node_tasks:
                    node_tasks.remove(task_id)

            cached.status = "deleted"

            internal_id = self._id_map.get(task_id)
            if internal_id:
                with contextlib.suppress(Exception):
                    self._run_async(self._repo.delete(internal_id))

            self._invalidate_cache(task_id)
            return {"success": True, "message": f"任务 {task_id} 已删除"}

    def cleanup_dead_nodes(self, timeout_seconds: int = 180) -> int:
        """清理超时未完成分配的任务"""
        with self._lock:
            current_time = time.time()
            requeued = 0

            for node_id, task_list in list(self._assigned_tasks.items()):
                still_assigned = []
                for tid in task_list:
                    cached = self._cache.get(tid)
                    if cached and cached.status == "assigned":
                        assigned_at = cached.assigned_at or current_time
                        if current_time - assigned_at > timeout_seconds:
                            cached.status = "pending"
                            cached.assigned_node = None
                            cached.assigned_at = None
                            self._pending_tasks.append(tid)
                            requeued += 1
                        else:
                            still_assigned.append(tid)
                    elif cached and cached.status in ("running",):
                        still_assigned.append(tid)

                if still_assigned:
                    self._assigned_tasks[node_id] = still_assigned
                else:
                    del self._assigned_tasks[node_id]

            self._stats["last_cleanup"] = current_time
            return requeued

    async def close(self) -> None:
        """关闭数据库连接和线程池"""
        if self._repo:
            await self._repo.close()
            self._initialized = False
        with self._executor_lock:
            if self._executor:
                self._executor.shutdown(wait=False)
                self._executor = None

    def __del__(self):
        """析构时清理资源"""
        try:
            if self._executor:
                self._executor.shutdown(wait=False)
        except Exception:
            pass


__all__ = ["PersistentTaskStorage", "CachedTaskInfo"]

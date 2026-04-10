"""
scheduler/simple_server.py
优化版任务调度器 - 修复节点显示问题
"""

import asyncio
import atexit
import concurrent.futures
import os
import sys
import threading
import time
import uuid
from collections import defaultdict
from typing import Any, Optional

from fastapi import BackgroundTasks, Body, FastAPI, HTTPException, Request
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from src.infrastructure.security.rate_limiter import setup_rate_limiting  # noqa: F401

    RATE_LIMITING_AVAILABLE = True
except ImportError:
    RATE_LIMITING_AVAILABLE = False

# 导入统一沙箱（新架构）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from src.infrastructure.sandbox.sandbox import BasicSandbox, SandboxConfig

    SANDBOX_AVAILABLE = True
except ImportError:
    from sandbox import CodeSandbox

    SANDBOX_AVAILABLE = False
    print("Warning: Using legacy sandbox, consider migrating to new architecture")


# ==================== 数据模型定义 ====================
class TaskSubmission(BaseModel):
    """任务提交模型"""

    code: str
    timeout: Optional[int] = 300
    resources: Optional[dict[str, Any]] = {"cpu": 1.0, "memory": 512}
    user_id: Optional[str] = None


class TaskResult(BaseModel):
    """任务结果模型"""

    task_id: int
    result: str
    node_id: Optional[str] = None


class TaskInfo(BaseModel):
    """任务信息模型"""

    task_id: int
    code: str
    status: str  # pending, assigned, running, completed, failed, deleted
    created_at: float
    assigned_at: Optional[float] = None
    assigned_node: Optional[str] = None
    completed_at: Optional[float] = None
    result: Optional[str] = None
    required_resources: dict[str, Any] = {"cpu": 1.0, "memory": 512}
    user_id: Optional[str] = None


class NodeRegistration(BaseModel):
    """节点注册模型"""

    node_id: str
    capacity: dict[str, Any]
    tags: Optional[dict[str, Any]] = {}


class NodeHeartbeat(BaseModel):
    """节点心跳模型 - 优化版"""

    node_id: str
    current_load: dict[str, Any]
    is_idle: bool
    available_resources: dict[str, Any]
    # 新增字段
    cpu_usage: Optional[float] = 0.0
    memory_usage: Optional[float] = 0.0
    is_available: Optional[bool] = True  # 节点是否可用（即使忙）


# ==================== 优化的内存存储类 ====================
class OptimizedMemoryStorage:
    """优化版内存存储，修复节点显示问题"""

    def __init__(self):
        # 任务存储
        self.tasks: dict[int, TaskInfo] = {}
        self.task_id_counter = 1

        # 节点管理 - 优化数据结构
        self.nodes: dict[str, dict] = {}
        self.node_heartbeats: dict[str, float] = {}
        self.node_status: dict[str, dict] = {}  # 新增：节点状态缓存

        # 调度队列
        self.pending_tasks: list[int] = []
        self.assigned_tasks: dict[str, list[int]] = defaultdict(list)

        self.server_id = str(uuid.uuid4())[:8]
        self.lock = threading.RLock()

        # 统计信息
        self.stats = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "nodes_registered": 0,
            "nodes_dropped": 0,
            "last_cleanup": time.time(),
        }

    # ========== 任务管理方法 ==========
    def add_task(
        self,
        code: str,
        timeout: int = 300,
        resources: Optional[dict] = None,
        user_id: Optional[str] = None,
    ) -> int:
        """添加新任务"""
        with self.lock:
            task_id = self.task_id_counter
            self.task_id_counter += 1

            task = TaskInfo(
                task_id=task_id,
                code=code,
                status="pending",
                created_at=time.time(),
                required_resources=resources or {"cpu": 1.0, "memory": 512},
                user_id=user_id,
            )

            self.tasks[task_id] = task
            self.pending_tasks.append(task_id)

            # 立即尝试调度
            self._schedule_tasks()

            return task_id

    def get_task_for_node(self, node_id: str) -> Optional[TaskInfo]:
        """为节点获取任务"""
        with self.lock:
            # 检查节点状态（使用新的三状态判断）
            node_status = self._get_node_status(node_id)
            if node_status["status"] != "online_available":
                return None

            node_info = self.nodes.get(node_id, {})
            node_info.get("available_resources", {})

            # 寻找匹配任务
            best_task = None
            best_score = -1

            for task_id in list(self.pending_tasks):
                task = self.tasks.get(task_id)
                if not task or task.status != "pending":
                    continue

                if self._can_node_handle_task(node_info, task):
                    score = self._calculate_match_score(node_info, task)
                    if score > best_score:
                        best_score = score
                        best_task = task

            if best_task:
                # 分配任务
                best_task.status = "assigned"
                best_task.assigned_node = node_id
                best_task.assigned_at = time.time()
                self.pending_tasks.remove(best_task.task_id)
                self.assigned_tasks[node_id].append(best_task.task_id)

                # 更新节点负载
                self._update_node_load(node_id, best_task, "add")

                self.stats["tasks_processed"] += 1

            return best_task

    def complete_task(self, task_id: int, result: str, node_id: Optional[str] = None) -> bool:
        """完成任务"""
        with self.lock:
            if task_id not in self.tasks:
                return False

            task = self.tasks[task_id]
            if task.status not in ["pending", "assigned", "running"]:
                return False

            # 更新任务状态
            task.status = "completed"
            task.completed_at = time.time()
            task.result = result

            # 释放节点资源
            actual_node_id = node_id or task.assigned_node
            if actual_node_id:
                self._update_node_load(actual_node_id, task, "remove")

            return True

    # ========== 节点管理方法 - 关键修复 ==========
    def register_node(self, registration: NodeRegistration) -> bool:
        """注册节点"""
        with self.lock:
            node_id = registration.node_id

            # 节点信息
            self.nodes[node_id] = {
                "capacity": registration.capacity,
                "tags": registration.tags,
                "registered_at": time.time(),
                "last_heartbeat": time.time(),
                "current_load": {"cpu_usage": 0.0, "memory_usage": 0},
                "available_resources": registration.capacity.copy(),
                "is_idle": True,
                "is_available": True,  # 新增：默认可用
            }

            # 更新心跳和状态
            self.node_heartbeats[node_id] = time.time()
            self._update_node_status_cache(node_id, "online_idle")

            self.stats["nodes_registered"] += 1
            return True

    def update_node_heartbeat(self, heartbeat: NodeHeartbeat) -> bool:
        """更新节点心跳 - 关键修复"""
        with self.lock:
            node_id = heartbeat.node_id

            if node_id not in self.nodes:
                return False

            node_info = self.nodes[node_id]

            # 更新基本信息
            node_info.update(
                {
                    "last_heartbeat": time.time(),
                    "current_load": heartbeat.current_load,
                    "is_idle": heartbeat.is_idle,
                    "available_resources": heartbeat.available_resources,
                    "is_available": (
                        heartbeat.is_available if hasattr(heartbeat, "is_available") else True
                    ),
                }
            )

            # 更新心跳时间
            self.node_heartbeats[node_id] = time.time()

            # 🎯 关键修复：更新节点状态缓存
            self._update_node_status_cache(node_id)

            return True

    def _get_node_status(self, node_id: str) -> dict[str, Any]:
        """获取节点状态 - 三状态判断"""
        if node_id not in self.nodes:
            return {"status": "offline", "reason": "not_registered"}

        node_info = self.nodes[node_id]
        last_heartbeat = self.node_heartbeats.get(node_id, 0)
        current_time = time.time()

        # 1. 检查是否完全离线
        if current_time - last_heartbeat > 120:  # 2分钟无心跳 = 离线
            return {"status": "offline", "reason": "no_heartbeat"}

        # 2. 检查是否在线但忙碌
        is_idle = node_info.get("is_idle", False)
        is_available = node_info.get("is_available", True)

        # 获取资源使用情况
        cpu_usage = node_info.get("current_load", {}).get("cpu_usage", 0)
        memory_usage = node_info.get("current_load", {}).get("memory_usage", 0)
        cpu_capacity = node_info.get("capacity", {}).get("cpu", 1.0)
        memory_capacity = node_info.get("capacity", {}).get("memory", 1024)

        cpu_percent = (cpu_usage / max(1.0, cpu_capacity)) * 100
        memory_percent = (memory_usage / max(1, memory_capacity)) * 100

        # 3. 判断具体状态
        if not is_available:
            return {"status": "online_unavailable", "reason": "node_unavailable"}
        elif cpu_percent > 90 or memory_percent > 95:
            return {
                "status": "online_busy",
                "reason": f"high_usage_cpu{cpu_percent:.0f}_mem{memory_percent:.0f}",
            }
        elif not is_idle:
            return {"status": "online_light", "reason": "user_active"}
        else:
            return {"status": "online_available", "reason": "idle_and_ready"}

    def _update_node_status_cache(self, node_id: str, forced_status: Optional[str] = None):
        """更新节点状态缓存"""
        if node_id not in self.nodes:
            return
        node_info = self.nodes[node_id]
        last_heartbeat = self.node_heartbeats.get(node_id, 0)
        current_time = time.time()

        if current_time - last_heartbeat > 180:  # 超过3分钟无心跳，直接标记为离线
            self.node_status[node_id] = {
                "status": "offline",
                "is_online": False,
                "is_idle": False,
                "reason": "心跳超时",
                "updated_at": current_time,
            }
            return
        is_idle = node_info.get("is_idle", False)
        is_available = node_info.get("is_available", True)

        if not is_available:
            status = "online_unavailable"
        elif not is_idle:
            status = "online_busy"
        else:
            status = "online_idle"

        self.node_status[node_id] = {
            "status": status,
            "is_online": True,
            "is_idle": is_idle,
            "reason": "在线" if is_idle else "忙碌",
            "updated_at": current_time,
        }

    def get_available_nodes(self, include_busy: bool = False) -> list[dict[str, Any]]:
        """获取可用节点"""
        with self.lock:
            available_nodes = []

            for node_id, node_info in self.nodes.items():
                status_info = self.node_status.get(node_id, {})
                status = status_info.get("status", "offline")

                # 根据参数决定包含哪些状态的节点
                if status == "offline" or not include_busy and status != "online_available":
                    continue

                # 构建节点信息
                node_data = {
                    "node_id": node_id,
                    "is_online": status_info.get("is_online", True),
                    "is_idle": status_info.get("is_idle", False),
                    "status": status,
                    "status_details": status_info,
                    "capacity": node_info.get("capacity", {}),
                    "tags": node_info.get("tags", {}),
                    "last_heartbeat": self.node_heartbeats.get(node_id, 0),
                    "current_load": node_info.get("current_load", {}),
                    "available_resources": node_info.get("available_resources", {}),
                }
                available_nodes.append(node_data)

            return available_nodes

    def cleanup_dead_nodes(self, timeout_seconds: int = 180):  # 改为3分钟
        """清理死亡节点"""
        with self.lock:
            current_time = time.time()
            dead_nodes = []

            for node_id, last_heartbeat in self.node_heartbeats.items():
                if current_time - last_heartbeat > timeout_seconds:
                    dead_nodes.append(node_id)

            for node_id in dead_nodes:
                # 重新分配任务
                if node_id in self.assigned_tasks:
                    for task_id in self.assigned_tasks[node_id]:
                        task = self.tasks.get(task_id)
                        if task and task.status == "assigned":
                            task.status = "pending"
                            task.assigned_node = None
                            task.assigned_at = None
                            self.pending_tasks.append(task_id)

                    del self.assigned_tasks[node_id]

                # 移除节点
                if node_id in self.nodes:
                    del self.nodes[node_id]
                if node_id in self.node_heartbeats:
                    del self.node_heartbeats[node_id]
                if node_id in self.node_status:
                    del self.node_status[node_id]

                self.stats["nodes_dropped"] += 1

            self.stats["last_cleanup"] = current_time
            return len(dead_nodes)

    # ========== 辅助方法 ==========
    def _schedule_tasks(self):
        """调度任务"""
        with self.lock:
            if not self.pending_tasks:
                return

            available_nodes = self.get_available_nodes()
            if not available_nodes:
                return

            for node_info in available_nodes:
                if self.pending_tasks:
                    self.get_task_for_node(node_info["node_id"])

    def _can_node_handle_task(self, node_info: dict, task: TaskInfo) -> bool:
        """检查节点是否能处理任务"""
        available = node_info.get("available_resources", {})
        required = task.required_resources

        if "cpu" in required and "cpu" in available and required["cpu"] > available.get("cpu", 0):
            return False

        return not (
            "memory" in required
            and "memory" in available
            and required["memory"] > available.get("memory", 0)
        )

    def _calculate_match_score(self, node_info: dict, task: TaskInfo) -> float:
        """计算匹配分数"""
        score = 0.0
        available = node_info.get("available_resources", {})
        required = task.required_resources

        if "cpu" in required and "cpu" in available:
            cpu_ratio = min(1.0, available.get("cpu", 0) / max(1.0, required["cpu"]))
            score += cpu_ratio * 0.4

        if "memory" in required and "memory" in available:
            mem_ratio = min(1.0, available.get("memory", 0) / max(1, required["memory"]))
            score += mem_ratio * 0.3

        if node_info.get("is_idle", False):
            score += 0.2

        current_load = node_info.get("current_load", {})
        cpu_load = current_load.get("cpu_usage", 0) / max(
            1.0, node_info.get("capacity", {}).get("cpu", 1)
        )
        score += (1.0 - min(1.0, cpu_load)) * 0.1

        return score

    def _update_node_load(self, node_id: str, task: TaskInfo, operation: str):
        """更新节点负载"""
        if node_id not in self.nodes:
            return

        node_info = self.nodes[node_id]
        if "current_load" not in node_info:
            node_info["current_load"] = {"cpu_usage": 0.0, "memory_usage": 0}

        cpu_needed = task.required_resources.get("cpu", 1.0)
        memory_needed = task.required_resources.get("memory", 512)

        if operation == "add":
            node_info["current_load"]["cpu_usage"] += cpu_needed
            node_info["current_load"]["memory_usage"] += memory_needed
        elif operation == "remove":
            node_info["current_load"]["cpu_usage"] = max(
                0, node_info["current_load"]["cpu_usage"] - cpu_needed
            )
            node_info["current_load"]["memory_usage"] = max(
                0, node_info["current_load"]["memory_usage"] - memory_needed
            )

    # ========== API方法 ==========
    def delete_task(self, task_id: int) -> dict[str, Any]:
        """删除任务"""
        with self.lock:
            if task_id not in self.tasks:
                return {"success": False, "error": "任务不存在"}

            task = self.tasks[task_id]

            if task.status not in ["pending", "assigned"]:
                return {
                    "success": False,
                    "error": f"只能删除pending或assigned状态的任务，当前状态: {task.status}",
                }

            if task.status == "pending" and task_id in self.pending_tasks:
                self.pending_tasks.remove(task_id)
            elif (
                task.status == "assigned"
                and task.assigned_node
                and task_id in self.assigned_tasks[task.assigned_node]
            ):
                self.assigned_tasks[task.assigned_node].remove(task_id)

            task.status = "deleted"
            return {"success": True, "message": f"任务 {task_id} 已删除"}

    def get_task_status(self, task_id: int) -> Optional[dict[str, Any]]:
        """获取任务状态"""
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        return {
            "task_id": task.task_id,
            "status": task.status,
            "result": task.result,
            "created_at": task.created_at,
            "assigned_at": task.assigned_at,
            "assigned_node": task.assigned_node,
            "completed_at": task.completed_at,
            "required_resources": task.required_resources,
            "user_id": task.user_id,
        }

    def get_all_results(self) -> list[dict[str, Any]]:
        """获取所有结果"""
        with self.lock:
            return [
                {
                    "task_id": task.task_id,
                    "result": task.result,
                    "completed_at": task.completed_at,
                    "assigned_node": task.assigned_node,
                    "user_id": task.user_id,
                }
                for task in self.tasks.values()
                if task.status == "completed"
            ]

    def get_system_stats(self) -> dict[str, Any]:
        """获取系统统计"""
        with self.lock:
            total_tasks = len(self.tasks)
            completed = sum(1 for t in self.tasks.values() if t.status == "completed")
            pending = len(self.pending_tasks)
            assigned = sum(len(tasks) for tasks in self.assigned_tasks.values())

            # 节点统计 - 使用新的状态判断
            total_nodes = len(self.nodes)
            online_nodes = 0
            available_nodes = 0

            for node_id in self.nodes:
                status_info = self._get_node_status(node_id)
                status = status_info["status"]

                if status != "offline":
                    online_nodes += 1
                    if status == "online_available":
                        available_nodes += 1

            return {
                "tasks": {
                    "total": total_tasks,
                    "completed": completed,
                    "pending": pending,
                    "assigned": assigned,
                    "failed": total_tasks - completed - pending - assigned,
                },
                "nodes": {
                    "total": total_nodes,
                    "online": online_nodes,  # 包括所有非离线状态
                    "available": available_nodes,  # 真正可用的
                    "offline": total_nodes - online_nodes,
                },
                "scheduler": self.stats,
            }

    def stop_node(self, node_id: str) -> dict[str, Any]:
        """停止节点"""
        with self.lock:
            if node_id not in self.nodes:
                return {"success": False, "error": "节点不存在"}

            # 重新分配任务
            if node_id in self.assigned_tasks:
                for task_id in self.assigned_tasks[node_id]:
                    task = self.tasks.get(task_id)
                    if task and task.status == "assigned":
                        task.status = "pending"
                        task.assigned_node = None
                        task.assigned_at = None
                        self.pending_tasks.append(task_id)

                del self.assigned_tasks[node_id]

            # 移除节点
            del self.nodes[node_id]
            if node_id in self.node_heartbeats:
                del self.node_heartbeats[node_id]
            if node_id in self.node_status:
                del self.node_status[node_id]

            self.stats["nodes_dropped"] += 1

            return {"success": True, "message": f"节点 {node_id} 已停止"}


# ==================== 持久化存储统一包装类 ====================
class PersistentSchedulerStorage:
    """
    统一持久化存储包装类

    组合 PersistentTaskStorage (任务) 和 PersistentNodeStorage (节点)，
    提供与 OptimizedMemoryStorage 完全相同的同步接口。
    内部通过线程池桥接 PersistentNodeStorage 的异步方法。
    """

    def __init__(self, db_path=None):
        from src.infrastructure.persistence.persistent_node_storage import PersistentNodeStorage
        from src.infrastructure.persistence.persistent_task_storage import PersistentTaskStorage

        self.task_storage = PersistentTaskStorage(db_path=db_path)
        self.node_storage = PersistentNodeStorage(db_path=db_path)

        self.server_id = str(uuid.uuid4())[:8]
        self.lock = threading.RLock()

        self._node_executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
        _executor_lock = threading.Lock()

        self._stats = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "nodes_registered": 0,
            "nodes_dropped": 0,
            "last_cleanup": time.time(),
        }

    def init_sync(self):
        """同步初始化：启动时调用，初始化任务和节点存储"""
        print("[持久化] 正在初始化 SQLite 持久化存储...")
        try:
            self.task_storage.init_sync()
            print("[持久化] 任务存储初始化完成")
        except Exception as e:
            print(f"[持久化] 任务存储初始化失败: {e}")
            raise

        try:
            self._run_node_async(self.node_storage._ensure_init())
            print("[持久化] 节点存储初始化完成")
        except Exception as e:
            print(f"[持久化] 节点存储初始化失败: {e}")
            raise

        print(f"[持久化] 存储后端: SQLite | 服务器ID: {self.server_id}")
        return self

    def shutdown(self):
        """优雅关闭：刷新缓存并关闭数据库连接"""
        print("[持久化] 正在关闭持久化存储...")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.task_storage.close())
            finally:
                loop.close()
        except Exception as e:
            print(f"[持久化] 关闭任务存储异常: {e}")

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.node_storage.close())
            finally:
                loop.close()
        except Exception as e:
            print(f"[持久化] 关闭节点存储异常: {e}")

        if self._node_executor:
            self._node_executor.shutdown(wait=False)
            self._node_executor = None

        print("[持久化] 持久化存储已关闭")

    def _run_node_async(self, coro):
        """在专用线程中运行节点存储的异步协程"""
        if self._node_executor is None:
            self._node_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="persistent_node_storage"
            )

        def _run_in_thread(c):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(c)
            finally:
                loop.close()

        future = self._node_executor.submit(_run_in_thread, coro)
        return future.result(timeout=30)

    # ========== 任务管理方法（委托给 task_storage）==========
    def add_task(
        self,
        code: str,
        timeout: int = 300,
        resources: Optional[dict] = None,
        user_id: Optional[str] = None,
    ) -> int:
        return self.task_storage.add_task(code, timeout, resources, user_id)

    def get_task_for_node(self, node_id: str) -> Optional[Any]:
        return self.task_storage.get_task_for_node(node_id)

    def complete_task(self, task_id: int, result: str, node_id: Optional[str] = None) -> bool:
        return self.task_storage.complete_task(task_id, result, node_id)

    def get_task_status(self, task_id: int) -> Optional[dict[str, Any]]:
        return self.task_storage.get_task_status(task_id)

    def get_all_results(self) -> list[dict[str, Any]]:
        return self.task_storage.get_all_results()

    def delete_task(self, task_id: int) -> dict[str, Any]:
        return self.task_storage.delete_task(task_id)

    # ========== 节点管理方法（委托给 node_storage，同步包装）==========
    def register_node(self, registration) -> bool:
        from src.infrastructure.persistence.persistent_node_storage import (
            NodeRegistration as PNodeRegistration,
        )

        reg = PNodeRegistration(
            node_id=registration.node_id,
            capacity=registration.capacity,
            tags={str(k): str(v) for k, v in (registration.tags or {}).items()},
        )
        result = self._run_node_async(self.node_storage.register_node(reg))
        if result:
            self._stats["nodes_registered"] += 1
        return result

    def update_node_heartbeat(self, heartbeat) -> bool:
        from src.infrastructure.persistence.persistent_node_storage import (
            NodeHeartbeat as PNodeHeartbeat,
        )

        hb = PNodeHeartbeat(
            node_id=heartbeat.node_id,
            current_load=heartbeat.current_load,
            is_idle=heartbeat.is_idle,
            is_available=getattr(heartbeat, "is_available", True),
            available_resources=heartbeat.available_resources,
        )
        return self._run_node_async(self.node_storage.update_node_heartbeat(hb))

    def _get_node_status(self, node_id: str) -> dict[str, Any]:
        """获取节点状态 - 三状态判断（兼容 OptimizedMemoryStorage 接口）"""
        node_data = self._run_node_async(self.node_storage.get_node(node_id))
        if node_data is None:
            return {"status": "offline", "reason": "not_registered"}

        status_str = node_data.get("status", "offline")
        is_idle = node_data.get("is_idle", False)
        is_available = node_data.get("is_available", True)

        if status_str == "offline":
            return {"status": "offline", "reason": "no_heartbeat"}
        elif not is_available:
            return {"status": "online_unavailable", "reason": "node_unavailable"}
        elif not is_idle:
            return {"status": "online_busy", "reason": "user_active"}
        else:
            return {"status": "online_available", "reason": "idle_and_ready"}

    def _update_node_status_cache(self, node_id: str, forced_status: Optional[str] = None):
        pass

    def get_available_nodes(self, include_busy: bool = False) -> list[dict[str, Any]]:
        raw_nodes = self._run_node_async(
            self.node_storage.get_available_nodes(include_busy=include_busy)
        )
        result = []
        for n in raw_nodes:
            status_info = self._get_node_status(n.get("node_id", ""))
            result.append(
                {
                    "node_id": n.get("node_id", ""),
                    "is_online": status_info["status"] != "offline",
                    "is_idle": n.get("is_idle", False),
                    "status": status_info["status"],
                    "status_details": status_info,
                    "capacity": n.get("capacity", {}),
                    "tags": n.get("tags", {}),
                    "last_heartbeat": n.get("last_heartbeat", 0),
                    "current_load": n.get("current_load", {}),
                    "available_resources": n.get("available_resources", {}),
                }
            )
        return result

    def cleanup_dead_nodes(self, timeout_seconds: int = 180) -> int:
        task_cleaned = self.task_storage.cleanup_dead_nodes(timeout_seconds)
        node_cleaned = self._run_node_async(self.node_storage.cleanup_dead_nodes(timeout_seconds))
        self._stats["nodes_dropped"] += node_cleaned
        self._stats["last_cleanup"] = time.time()
        return task_cleaned + node_cleaned

    def stop_node(self, node_id: str) -> dict[str, Any]:
        result = self._run_node_async(self.node_storage.stop_node(node_id))
        if result.get("success"):
            self._stats["nodes_dropped"] += 1
        return result

    # ========== 兼容属性（供外部直接访问）==========
    @property
    def tasks(self):
        return self.task_storage._cache

    @property
    def task_id_counter(self):
        return self.task_storage._task_id_counter

    @task_id_counter.setter
    def task_id_counter(self, value):
        self.task_storage._task_id_counter = value

    @property
    def nodes(self):
        return {}

    @property
    def node_heartbeats(self):
        return {}

    @property
    def node_status(self):
        return {}

    @property
    def pending_tasks(self):
        return self.task_storage._pending_tasks

    @property
    def assigned_tasks(self):
        return self.task_storage._assigned_tasks

    # ========== API 方法 ==========
    def get_system_stats(self) -> dict[str, Any]:
        task_stats = self.task_storage.get_system_stats()
        with self.lock:
            all_nodes = self._run_node_async(self.node_storage.get_all_nodes())
            total_nodes = len(all_nodes)
            online_nodes = sum(1 for n in all_nodes if n.get("status") != "offline")
            available_nodes = sum(
                1 for n in all_nodes if n.get("status") != "offline" and n.get("is_idle", False)
            )

            return {
                "tasks": task_stats.get("tasks", {}),
                "nodes": {
                    "total": total_nodes,
                    "online": online_nodes,
                    "available": available_nodes,
                    "offline": total_nodes - online_nodes,
                },
                "scheduler": self._stats,
                "persistence": task_stats.get("persistence", {}),
            }

    def _is_node_online(self, node_id: str) -> bool:
        status = self._get_node_status(node_id)
        return status["status"] != "offline"

    def _schedule_tasks(self):
        pass

    def _can_node_handle_task(self, node_info: dict, task: Any) -> bool:
        return True

    def _calculate_match_score(self, node_info: dict, task: Any) -> float:
        return 1.0

    def _update_node_load(self, node_id: str, task: Any, operation: str):
        pass


# ==================== FastAPI 应用 ====================
app = FastAPI(
    title="优化版闲置计算调度器", description="修复节点显示问题，增强稳定性", version="2.0.0"
)

rate_limiter = None
if RATE_LIMITING_AVAILABLE:
    try:
        from slowapi import Limiter
        from slowapi.errors import RateLimitExceeded
        from slowapi.util import get_remote_address

        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=["60/minute"],
        )
        app.state.limiter = limiter

        @app.exception_handler(RateLimitExceeded)
        async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
            from slowapi import _rate_limit_exceeded_handler

            response = _rate_limit_exceeded_handler(request, exc)
            return response

        rate_limiter = limiter
        print("[调度器] 限流中间件已启用")
    except Exception as e:
        print(f"[警告] 限流器初始化失败: {e}")


def rate_limit(limit_value: str):
    """限流装饰器辅助函数"""

    def decorator(func):
        if rate_limiter:
            return rate_limiter.limit(limit_value)(func)
        return func

    return decorator


def _shutdown_persistent_storage():
    """关闭钩子：优雅关闭持久化存储"""
    if isinstance(storage, PersistentSchedulerStorage):
        try:
            storage.shutdown()
        except Exception as e:
            print(f"[警告] 持久化存储关闭异常: {e}")


# 初始化存储（支持持久化后端选择）
backend = os.getenv("STORAGE_BACKEND", "sqlite").strip().lower()
_storage_instance = None

if backend == "sqlite":
    print("[调度器] 存储后端: SQLite (持久化模式)")
    try:
        _storage_instance = PersistentSchedulerStorage()
        _storage_instance.init_sync()
        atexit.register(_shutdown_persistent_storage)
    except Exception as e:
        print(f"[警告] SQLite 持久化初始化失败: {e}")
        print("[警告] 自动降级到内存存储 (memory backend)")
        _storage_instance = OptimizedMemoryStorage()
elif backend == "memory":
    print("[调度器] 存储后端: Memory (内存模式)")
    _storage_instance = OptimizedMemoryStorage()
else:
    print(f"[警告] 未知的存储后端 '{backend}'，使用默认内存存储")
    _storage_instance = OptimizedMemoryStorage()

storage = _storage_instance


# 初始化沙箱（优先使用新架构）
if SANDBOX_AVAILABLE:
    sandbox = BasicSandbox(SandboxConfig(timeout=300, memory_limit=512))
else:
    sandbox = CodeSandbox()


# ==================== 后台任务 ====================
def periodic_cleanup():
    """定期清理"""
    try:
        cleaned = storage.cleanup_dead_nodes(timeout_seconds=180)
        if cleaned > 0:
            print(f"[清理] 移除了 {cleaned} 个死亡节点")
    except Exception as e:
        print(f"[清理错误] {e}")


@app.on_event("startup")
def startup_event():
    """启动事件"""
    print("=" * 60)
    print("优化版任务调度器 v2.0.0")
    print(f"服务器ID: {storage.server_id}")
    print(f"存储后端: {backend}")
    if isinstance(storage, PersistentSchedulerStorage):
        persistence_info = storage.get_system_stats().get("persistence", {})
        print(f"数据库路径: {persistence_info.get('db_path', 'N/A')}")
        print(f"缓存任务数: {persistence_info.get('cached_tasks', 0)}")
    print("功能: 节点三状态判断、智能调度、稳定显示、SQLite持久化")
    print("=" * 60)


@app.on_event("shutdown")
def shutdown_event():
    """关闭事件"""
    if isinstance(storage, PersistentSchedulerStorage):
        storage.shutdown()


# ==================== API端点 ====================
@app.get("/")
async def root():
    """根端点"""
    stats = storage.get_system_stats()
    return {
        "service": "优化版闲置计算调度器",
        "status": "运行中",
        "version": "2.0.0",
        "server_id": storage.server_id,
        **stats,
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    stats = storage.get_system_stats()
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "server_id": storage.server_id,
        "nodes": stats["nodes"],
        "tasks": {"pending": stats["tasks"]["pending"], "assigned": stats["tasks"]["assigned"]},
    }


@app.post("/submit")
@rate_limit("10/minute")
async def submit_task(
    request: Request, submission: TaskSubmission, background_tasks: BackgroundTasks
):
    """提交任务 - 限流: 10次/分钟"""
    if not submission.code.strip():
        raise HTTPException(status_code=400, detail="代码不能为空")

    # 安全检查
    safety_check = sandbox.check_code_safety(submission.code)
    if not safety_check["safe"]:
        raise HTTPException(status_code=400, detail=f"代码安全检查失败: {safety_check['error']}")

    task_id = storage.add_task(
        submission.code, submission.timeout, submission.resources, submission.user_id
    )

    background_tasks.add_task(periodic_cleanup)

    return {
        "task_id": task_id,
        "status": "submitted",
        "message": f"任务 {task_id} 已加入队列",
        "safety_check": "通过",
    }


@app.get("/get_task")
async def get_task(node_id: Optional[str] = None):
    """获取任务"""
    if node_id:
        task = storage.get_task_for_node(node_id)
    else:
        # 兼容模式
        with storage.lock:
            for task_id in list(storage.pending_tasks):
                task_info = storage.tasks.get(task_id)
                if task_info and task_info.status == "pending":
                    task_info.status = "running"
                    storage.pending_tasks.remove(task_id)
                    task = task_info
                    break
            else:
                task = None

    if task is None:
        return {"task_id": None, "code": None, "status": "no_tasks"}

    return {
        "task_id": task.task_id,
        "code": task.code,
        "status": "assigned",
        "assigned_node": task.assigned_node,
    }


@app.post("/submit_result")
async def submit_result(result: TaskResult):
    """提交结果"""
    success = storage.complete_task(result.task_id, result.result, result.node_id)

    if not success:
        raise HTTPException(status_code=404, detail="任务未找到或无法完成")

    return {"success": True, "task_id": result.task_id, "message": f"任务 {result.task_id} 完成"}


@app.get("/status/{task_id}")
async def get_status(task_id: int):
    """获取任务状态"""
    status = storage.get_task_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="任务未找到")
    return status


@app.get("/results")
async def get_results():
    """获取所有结果"""
    results = storage.get_all_results()
    return {"count": len(results), "results": results}


@app.get("/stats")
async def get_stats():
    """获取统计"""
    return storage.get_system_stats()


# ==================== 节点管理API ====================
@app.post("/api/nodes/register")
@rate_limit("5/minute")
async def register_node(request: Request, registration: NodeRegistration):
    """注册节点 - 限流: 5次/分钟"""
    success = storage.register_node(registration)
    if not success:
        raise HTTPException(status_code=500, detail="注册失败")

    return {
        "status": "registered",
        "node_id": registration.node_id,
        "message": f"节点 {registration.node_id} 注册成功",
    }


@app.post("/api/nodes/{node_id}/heartbeat")
async def update_heartbeat(node_id: str, heartbeat: NodeHeartbeat):
    """更新心跳"""
    if heartbeat.node_id != node_id:
        raise HTTPException(status_code=400, detail="节点ID不匹配")

    success = storage.update_node_heartbeat(heartbeat)
    if not success:
        raise HTTPException(status_code=404, detail="节点未找到")

    return {"status": "updated", "node_id": node_id, "timestamp": time.time()}


@app.get("/api/nodes")
async def list_nodes(online_only: bool = True):
    """列出节点"""
    try:
        if online_only:
            nodes = storage.get_available_nodes(include_busy=False)
        else:
            with storage.lock:
                nodes = []
                for node_id, node_info in storage.nodes.items():
                    status_info = storage._get_node_status(node_id)
                    nodes.append(
                        {
                            "node_id": node_id,
                            **node_info,
                            "status": status_info["status"],
                            "status_details": status_info,
                        }
                    )

        return {"count": len(nodes), "nodes": nodes, "online_only": online_only}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取节点失败: {str(e)}") from e


@app.post("/api/nodes/activate-local")
@rate_limit("5/minute")
async def activate_local_node(request: Request, config: dict = Body(...)):
    """激活本地节点 - 限流: 5次/分钟"""
    try:
        import uuid

        node_id = f"local-{uuid.uuid4().hex[:8]}-{int(time.time())}"

        capacity = {
            "cpu": config.get("cpu_limit", 4.0),
            "memory": config.get("memory_limit", 8192),
            "disk": config.get("storage_limit", 10240),
        }

        registration = NodeRegistration(
            node_id=node_id,
            capacity=capacity,
            tags={
                "type": "local",
                "platform": "local-web-activated",
                "auto_activated": True,
                "user_id": config.get("user_id", "unknown"),
            },
        )

        success = storage.register_node(registration)
        if not success:
            raise HTTPException(status_code=500, detail="注册失败")

        # 发送初始心跳
        heartbeat = NodeHeartbeat(
            node_id=node_id,
            current_load={"cpu_usage": 0.0, "memory_usage": 0},
            is_idle=True,
            available_resources=capacity,
            is_available=True,
        )

        storage.update_node_heartbeat(heartbeat)

        return {
            "success": True,
            "node_id": node_id,
            "capacity": capacity,
            "message": f"本地节点 {node_id} 激活成功",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"激活失败: {str(e)}") from e


@app.post("/api/nodes/{node_id}/stop")
async def stop_node_api(node_id: str):
    """停止节点"""
    result = storage.stop_node(node_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.delete("/api/tasks/{task_id}")
async def delete_task_api(task_id: int):
    """删除任务"""
    result = storage.delete_task(task_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ==================== CORS 支持 ====================
try:
    from fastapi.middleware.cors import CORSMiddleware

    _cors_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:8000")
    _cors_origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()]
    _allow_all = "*" in _cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if _allow_all else _cors_origins,
        allow_credentials=not _allow_all,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    print(f"[调度器] CORS中间件已启用 (origins={_cors_origins})")
except ImportError:
    print("[调度器] CORS中间件不可用")

# ==================== 启动 ====================
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", os.getenv("SCHEDULER_PORT", "8000")))
    host = os.getenv("HOST", "0.0.0.0")

    print(f"[调度器] 启动服务器: http://{host}:{port}")
    print(f"[调度器] 服务器ID: {storage.server_id}")
    print("[调度器] 提示: 可通过环境变量 PORT 或 SCHEDULER_PORT 修改端口")

    uvicorn.run(app, host=host, port=port, log_level="info")
# ==================== 节点显示修复模块 ====================
# 这个模块可以直接添加到文件末尾，不需要依赖原类定义

from typing import Any  # noqa: E402


class NodeStatusFix:
    """节点状态修复类 - 独立运行"""

    def __init__(self, storage_instance):
        self.storage = storage_instance
        self.original_methods = {}
        self.fixes_applied = False

    def apply_all_fixes(self):
        """应用所有修复"""
        print("=" * 60)
        print("应用节点显示修复...")
        print("=" * 60)

        # 保存原方法
        self._save_original_methods()

        # 应用修复
        self._fix_is_node_online()
        self._fix_cleanup_dead_nodes()

        # 启动监控
        self._start_monitoring()

        self.fixes_applied = True

        print("=" * 60)
        print("修复完成!")
        print("1. 心跳超时延长至120-180秒")
        print("2. 即使is_idle=false也显示在线")
        print("3. 节点状态监控已启用")
        print("=" * 60)

    def _save_original_methods(self):
        """保存原方法"""
        if hasattr(self.storage, "_is_node_online"):
            self.original_methods["_is_node_online"] = self.storage._is_node_online

        if hasattr(self.storage, "cleanup_dead_nodes"):
            self.original_methods["cleanup_dead_nodes"] = self.storage.cleanup_dead_nodes

    def _fix_is_node_online(self):
        """修复_is_node_online方法"""

        def enhanced_is_node_online(node_id: str) -> bool:
            """
            增强版节点在线判断
            解决节点频繁显示为0的问题
            """
            # 基础检查
            if not hasattr(self.storage, "nodes") or node_id not in getattr(
                self.storage, "nodes", {}
            ):
                return False

            if not hasattr(self.storage, "node_heartbeats"):
                return False

            nodes = getattr(self.storage, "nodes", {})
            node_heartbeats = getattr(self.storage, "node_heartbeats", {})

            node_info = nodes.get(node_id, {})
            last_heartbeat = node_heartbeats.get(node_id, 0)
            current_time = time.time()

            # 🎯 关键修复：延长心跳超时
            time_since_last_heartbeat = current_time - last_heartbeat

            # 动态超时设置
            tags = node_info.get("tags", {})
            is_api_activated = tags.get("auto_activated", False)

            # 更长的超时时间
            max_timeout = 180 if is_api_activated else 120

            # 如果超过超时时间，返回False
            if time_since_last_heartbeat > max_timeout:
                return False

            # 🎯 关键修复：即使is_idle=false，也返回True（在线但忙碌）
            # 只要有心跳，就认为节点在线
            is_idle = node_info.get("is_idle", False)

            if not is_idle:
                # 节点忙碌但在线
                cpu_usage = node_info.get("current_load", {}).get("cpu_usage", 0)
                memory_usage = node_info.get("current_load", {}).get("memory_usage", 0)
                capacity = node_info.get("capacity", {})

                cpu_percent = (cpu_usage / max(1.0, capacity.get("cpu", 1))) * 100
                memory_percent = (memory_usage / max(1, capacity.get("memory", 1024))) * 100

                # 如果资源使用过高，记录但依然返回在线
                if cpu_percent > 95 or memory_percent > 98:
                    print(f"[修复] 节点 {node_id}: 在线但过载")
                else:
                    print(f"[修复] 节点 {node_id}: 在线但忙碌")

            return True

        # 应用修复
        self.storage._is_node_online = enhanced_is_node_online
        print("[修复] _is_node_online 方法已增强")

    def _fix_cleanup_dead_nodes(self):
        """修复cleanup_dead_nodes方法"""
        if "cleanup_dead_nodes" not in self.original_methods:
            return

        original_method = self.original_methods["cleanup_dead_nodes"]

        def enhanced_cleanup_dead_nodes(timeout_seconds: int = 180):
            """增强版清理死亡节点 - 更长的超时"""
            # 使用更长的默认超时
            actual_timeout = timeout_seconds if timeout_seconds > 60 else 180

            # 调用原方法但使用更长的超时
            return original_method(actual_timeout)

        # 应用修复
        self.storage.cleanup_dead_nodes = enhanced_cleanup_dead_nodes
        print("[修复] cleanup_dead_nodes 方法已增强")

    def _start_monitoring(self):
        """启动节点监控"""

        def monitor():
            while True:
                try:
                    self._log_node_status()
                    time.sleep(30)  # 每30秒记录一次
                except Exception as e:
                    print(f"[监控错误] {e}")
                    time.sleep(60)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        print("[修复] 节点状态监控已启动")

    def _log_node_status(self):
        """记录节点状态"""
        if not hasattr(self.storage, "nodes"):
            return

        nodes = getattr(self.storage, "nodes", {})
        total = len(nodes)

        if total == 0:
            print("[节点监控] 没有注册的节点")
            return

        # 统计在线节点
        online_count = 0
        for node_id in nodes:
            if self.storage._is_node_online(node_id):
                online_count += 1

        print(f"[节点监控] 总数: {total}, 在线: {online_count}, 离线: {total - online_count}")

        # 详细状态（只显示前5个节点）
        for _i, node_id in enumerate(list(nodes.keys())[:5]):
            is_online = self.storage._is_node_online(node_id)
            node_info = nodes.get(node_id, {})
            status = "🟢" if is_online else "🔴"
            idle = "空闲" if node_info.get("is_idle", False) else "忙碌"
            print(f"[节点监控] {status} {node_id[:10]}...: {idle}")


# ==================== API端点修复 ====================


def enhance_api_endpoints(app_instance, storage_instance):
    """增强API端点"""

    # 增强 /api/nodes 端点
    for route in app_instance.routes:
        if hasattr(route, "path") and route.path == "/api/nodes":
            original_endpoint = route.endpoint
            break
    else:
        print("[修复] 未找到 /api/nodes 端点")
        return

    async def enhanced_list_nodes(online_only: bool = True):
        """增强版节点列表"""
        try:
            # 调用原端点
            import inspect

            if inspect.iscoroutinefunction(original_endpoint):
                response = await original_endpoint(online_only)
            else:
                response = original_endpoint(online_only)

            # 确保节点有正确的is_online字段
            if "nodes" in response:
                nodes = response["nodes"]
                for node in nodes:
                    node_id = node.get("node_id")
                    if node_id:
                        # 使用修复后的方法判断在线状态
                        is_online = storage_instance._is_node_online(node_id)
                        node["is_online"] = is_online

            # 添加统计信息
            total_nodes = len(getattr(storage_instance, "nodes", {}))
            online_nodes = 0
            for node_id in getattr(storage_instance, "nodes", {}):
                if storage_instance._is_node_online(node_id):
                    online_nodes += 1

            response["enhanced_stats"] = {
                "total_nodes": total_nodes,
                "online_nodes": online_nodes,
                "fix_applied": True,
            }

            return response

        except Exception as e:
            print(f"[修复] 增强节点列表失败: {e}")
            import inspect

            if inspect.iscoroutinefunction(original_endpoint):
                return await original_endpoint(online_only)
            else:
                return original_endpoint(online_only)

    # 替换端点
    for route in app_instance.routes:
        if hasattr(route, "path") and route.path == "/api/nodes":
            route.endpoint = enhanced_list_nodes
            break

    print("[修复] /api/nodes 端点已增强")


# ==================== 添加调试端点 ====================


def add_debug_endpoints(app_instance, storage_instance):
    """添加调试端点"""
    import os

    enable_debug = os.getenv("ENABLE_DEBUG_ENDPOINTS", "false").lower() == "true"

    if not enable_debug:
        print("[调试端点] 已禁用 (设置 ENABLE_DEBUG_ENDPOINTS=true 启用)")
        return

    @app_instance.get("/api/debug/nodes-status")
    async def debug_nodes_status():
        """调试端点：节点状态"""
        try:
            nodes_info = []
            nodes = getattr(storage_instance, "nodes", {})
            node_heartbeats = getattr(storage_instance, "node_heartbeats", {})

            for node_id, node_info in nodes.items():
                is_online = storage_instance._is_node_online(node_id)
                last_heartbeat = node_heartbeats.get(node_id, 0)

                node_data = {
                    "node_id": node_id,
                    "is_online": is_online,
                    "last_heartbeat": last_heartbeat,
                    "time_since_heartbeat": time.time() - last_heartbeat,
                    "is_idle": node_info.get("is_idle", False),
                    "tags": node_info.get("tags", {}),
                }
                nodes_info.append(node_data)

            return {"count": len(nodes_info), "nodes": nodes_info, "fix_applied": True}

        except Exception as e:
            return {"error": str(e), "fix_applied": False}

    @app_instance.get("/api/debug/fix-status")
    async def debug_fix_status():
        """修复状态"""
        return {
            "status": "active",
            "fixes": [
                "enhanced_is_node_online",
                "enhanced_cleanup_dead_nodes",
                "enhanced_api_nodes",
                "node_monitoring",
            ],
            "timestamp": time.time(),
        }

    print("[调试端点] 已启用 (仅限开发环境使用)")


# ==================== 主修复函数 ====================


def apply_node_display_fix():
    """
    主修复函数
    在文件末尾调用此函数即可应用所有修复
    """
    print("=" * 60)
    print("节点显示修复系统 v1.0")
    print("=" * 60)

    # 检查必要的组件
    if "storage" not in globals():
        print("[错误] 未找到 storage 实例")
        return False

    if "app" not in globals():
        print("[错误] 未找到 app 实例")
        return False

    try:
        # 1. 创建修复器
        fixer = NodeStatusFix(storage)

        # 2. 应用修复
        fixer.apply_all_fixes()

        # 3. 增强API端点
        enhance_api_endpoints(app, storage)

        # 4. 添加调试端点
        add_debug_endpoints(app, storage)

        print("=" * 60)
        print("✅ 所有修复已成功应用!")
        print("访问以下端点验证:")
        print("  /api/debug/nodes-status - 节点状态")
        print("  /api/debug/fix-status - 修复状态")
        print("  /api/nodes - 增强版节点列表")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"[错误] 应用修复失败: {e}")
        import traceback

        traceback.print_exc()
        return False


# ==================== 自动应用修复 ====================

# 当这个模块被导入时，自动尝试应用修复
try:
    # 等待一小段时间，确保其他组件已初始化
    import threading

    def delayed_apply_fix():
        time.sleep(2)  # 等待2秒
        print("[自动修复] 正在应用节点显示修复...")
        apply_node_display_fix()

    # 在后台线程中应用修复
    fix_thread = threading.Thread(target=delayed_apply_fix, daemon=True)
    fix_thread.start()

    print("[提示] 节点显示修复系统已加载")
    print("[提示] 修复将在2秒后自动应用")

except Exception as e:
    print(f"[警告] 自动修复失败: {e}")

# ==================== 手动调用接口 ====================

# 如果需要手动触发修复，可以调用：
# apply_node_display_fix()

print("[完成] 节点显示修复模块加载完成")
print("=" * 60)

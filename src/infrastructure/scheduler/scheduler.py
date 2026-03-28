"""
统一调度器实现

整合基础调度和高级调度功能：
- SimpleScheduler: 简单FIFO调度
- AdvancedScheduler: 支持DRF、优先级、公平调度
"""

import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SchedulingPolicy(Enum):
    """调度策略枚举"""
    FIFO = "fifo"
    FAIR = "fair"
    PRIORITY = "priority"
    DRF = "drf"


@dataclass
class TaskInfo:
    """任务信息（兼容旧接口）"""
    task_id: int
    code: str
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    assigned_at: Optional[float] = None
    assigned_node: Optional[str] = None
    completed_at: Optional[float] = None
    result: Optional[str] = None
    required_resources: dict[str, Any] = field(default_factory=lambda: {"cpu": 1.0, "memory": 512})
    user_id: Optional[str] = None
    priority: int = 0


@dataclass
class NodeInfo:
    """节点信息（兼容旧接口）"""
    node_id: str
    capacity: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, Any] = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    current_load: dict[str, Any] = field(default_factory=lambda: {"cpu_usage": 0.0, "memory_usage": 0})
    available_resources: dict[str, Any] = field(default_factory=dict)
    is_idle: bool = True
    is_available: bool = True


class Predicate(ABC):
    """调度谓词基类"""

    @abstractmethod
    def evaluate(self, task: TaskInfo, node: NodeInfo) -> bool:
        """评估节点是否满足任务要求"""
        pass


class ResourcePredicate(Predicate):
    """资源谓词：检查节点资源是否满足任务需求"""

    def evaluate(self, task: TaskInfo, node: NodeInfo) -> bool:
        available = node.available_resources
        required = task.required_resources

        if "cpu" in required and "cpu" in available and required["cpu"] > available.get("cpu", 0):
            return False

        return not ("memory" in required and "memory" in available and required["memory"] > available.get("memory", 0))


class TagPredicate(Predicate):
    """标签谓词：检查节点标签是否匹配"""

    def __init__(self, required_tags: dict[str, Any]):
        self.required_tags = required_tags

    def evaluate(self, task: TaskInfo, node: NodeInfo) -> bool:
        return all(node.tags.get(key) == value for key, value in self.required_tags.items())


class PriorityPlugin(ABC):
    """优先级插件基类"""

    @abstractmethod
    def calculate_score(self, task: TaskInfo, node: NodeInfo) -> float:
        """计算任务在节点上的优先级分数"""
        pass


class ResourceBalancePlugin(PriorityPlugin):
    """资源均衡插件：优先选择资源最充足的节点"""

    def calculate_score(self, task: TaskInfo, node: NodeInfo) -> float:
        score = 0.0
        available = node.available_resources
        required = task.required_resources

        if "cpu" in required and "cpu" in available:
            cpu_ratio = min(1.0, available.get("cpu", 0) / max(1.0, required["cpu"]))
            score += cpu_ratio * 0.4

        if "memory" in required and "memory" in available:
            mem_ratio = min(1.0, available.get("memory", 0) / max(1, required["memory"]))
            score += mem_ratio * 0.3

        if node.is_idle:
            score += 0.2

        current_load = node.current_load
        cpu_load = current_load.get("cpu_usage", 0) / max(1.0, node.capacity.get("cpu", 1))
        score += (1.0 - min(1.0, cpu_load)) * 0.1

        return score


class BaseScheduler(ABC):
    """调度器基类"""

    @abstractmethod
    def add_task(self, task: TaskInfo) -> str:
        """添加任务"""
        pass

    @abstractmethod
    def get_task_for_node(self, node_id: str) -> Optional[TaskInfo]:
        """为节点获取任务"""
        pass

    @abstractmethod
    def complete_task(self, task_id: str, result: str) -> bool:
        """完成任务"""
        pass

    @abstractmethod
    def register_node(self, node: NodeInfo) -> bool:
        """注册节点"""
        pass

    @abstractmethod
    def update_node_heartbeat(self, node_id: str, heartbeat_data: dict[str, Any]) -> bool:
        """更新节点心跳"""
        pass


class SimpleScheduler(BaseScheduler):
    """
    简单调度器

    基于FIFO队列的简单调度实现
    适用于小规模部署和测试环境
    """

    def __init__(self):
        self.tasks: dict[str, TaskInfo] = {}
        self.task_id_counter = 1
        self.nodes: dict[str, NodeInfo] = {}
        self.node_heartbeats: dict[str, float] = {}
        self.pending_tasks: list[str] = []
        self.assigned_tasks: dict[str, list[str]] = defaultdict(list)
        self.lock = threading.RLock()
        self.predicates: list[Predicate] = [ResourcePredicate()]
        self.priority_plugins: list[PriorityPlugin] = [ResourceBalancePlugin()]

        self.stats = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "nodes_registered": 0,
            "nodes_dropped": 0,
        }

    def add_task(self, task: TaskInfo) -> str:
        with self.lock:
            if task.task_id == 0:
                task.task_id = self.task_id_counter
                self.task_id_counter += 1

            task_id_str = str(task.task_id)
            self.tasks[task_id_str] = task
            self.pending_tasks.append(task_id_str)

            self._schedule_tasks()

            return task_id_str

    def get_task_for_node(self, node_id: str) -> Optional[TaskInfo]:
        with self.lock:
            if node_id not in self.nodes:
                return None

            node_info = self.nodes[node_id]

            if not self._is_node_available(node_id):
                return None

            best_task = None
            best_score = -1

            for task_id in list(self.pending_tasks):
                task = self.tasks.get(task_id)
                if not task or task.status != "pending":
                    continue

                if self._evaluate_predicates(task, node_info):
                    score = self._calculate_priority(task, node_info)
                    if score > best_score:
                        best_score = score
                        best_task = task

            if best_task:
                best_task.status = "assigned"
                best_task.assigned_node = node_id
                best_task.assigned_at = time.time()
                self.pending_tasks.remove(str(best_task.task_id))
                self.assigned_tasks[node_id].append(str(best_task.task_id))

                self._update_node_load(node_id, best_task, "add")
                self.stats["tasks_processed"] += 1

            return best_task

    def complete_task(self, task_id: str, result: str) -> bool:
        with self.lock:
            if task_id not in self.tasks:
                return False

            task = self.tasks[task_id]
            if task.status not in ["pending", "assigned", "running"]:
                return False

            task.status = "completed"
            task.completed_at = time.time()
            task.result = result

            if task.assigned_node:
                self._update_node_load(task.assigned_node, task, "remove")

            return True

    def register_node(self, node: NodeInfo) -> bool:
        with self.lock:
            self.nodes[node.node_id] = node
            self.node_heartbeats[node.node_id] = time.time()
            self.stats["nodes_registered"] += 1
            return True

    def update_node_heartbeat(self, node_id: str, heartbeat_data: dict[str, Any]) -> bool:
        with self.lock:
            if node_id not in self.nodes:
                return False

            node_info = self.nodes[node_id]
            node_info.last_heartbeat = time.time()
            node_info.current_load = heartbeat_data.get("current_load", node_info.current_load)
            node_info.is_idle = heartbeat_data.get("is_idle", node_info.is_idle)
            node_info.available_resources = heartbeat_data.get("available_resources", node_info.available_resources)
            node_info.is_available = heartbeat_data.get("is_available", True)

            self.node_heartbeats[node_id] = time.time()

            return True

    def get_available_nodes(self, include_busy: bool = False) -> list[NodeInfo]:
        with self.lock:
            available_nodes = []

            for node_id, node_info in self.nodes.items():
                if not self._is_node_online(node_id):
                    continue

                if not include_busy and not self._is_node_available(node_id):
                    continue

                available_nodes.append(node_info)

            return available_nodes

    def cleanup_dead_nodes(self, timeout_seconds: int = 180) -> int:
        with self.lock:
            current_time = time.time()
            dead_nodes = []

            for node_id, last_heartbeat in self.node_heartbeats.items():
                if current_time - last_heartbeat > timeout_seconds:
                    dead_nodes.append(node_id)

            for node_id in dead_nodes:
                self._reassign_tasks(node_id)

                if node_id in self.nodes:
                    del self.nodes[node_id]
                if node_id in self.node_heartbeats:
                    del self.node_heartbeats[node_id]

                self.stats["nodes_dropped"] += 1

            return len(dead_nodes)

    def get_system_stats(self) -> dict[str, Any]:
        with self.lock:
            total_tasks = len(self.tasks)
            completed = sum(1 for t in self.tasks.values() if t.status == "completed")
            pending = len(self.pending_tasks)
            assigned = sum(len(tasks) for tasks in self.assigned_tasks.values())

            total_nodes = len(self.nodes)
            online_nodes = sum(1 for n in self.nodes if self._is_node_online(n))

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
                    "online": online_nodes,
                    "offline": total_nodes - online_nodes,
                },
                "scheduler": self.stats,
            }

    def _is_node_online(self, node_id: str) -> bool:
        if node_id not in self.node_heartbeats:
            return False

        last_heartbeat = self.node_heartbeats.get(node_id, 0)
        return time.time() - last_heartbeat <= 180

    def _is_node_available(self, node_id: str) -> bool:
        if not self._is_node_online(node_id):
            return False

        node_info = self.nodes.get(node_id)
        if not node_info:
            return False

        return node_info.is_available and node_info.is_idle

    def _evaluate_predicates(self, task: TaskInfo, node: NodeInfo) -> bool:
        return all(predicate.evaluate(task, node) for predicate in self.predicates)

    def _calculate_priority(self, task: TaskInfo, node: NodeInfo) -> float:
        total_score = 0.0
        for plugin in self.priority_plugins:
            total_score += plugin.calculate_score(task, node)
        return total_score

    def _update_node_load(self, node_id: str, task: TaskInfo, operation: str):
        if node_id not in self.nodes:
            return

        node_info = self.nodes[node_id]
        cpu_needed = task.required_resources.get("cpu", 1.0)
        memory_needed = task.required_resources.get("memory", 512)

        if "current_load" not in node_info.current_load:
            node_info.current_load = {"cpu_usage": 0.0, "memory_usage": 0}

        if operation == "add":
            node_info.current_load["cpu_usage"] += cpu_needed
            node_info.current_load["memory_usage"] += memory_needed
        elif operation == "remove":
            node_info.current_load["cpu_usage"] = max(0, node_info.current_load["cpu_usage"] - cpu_needed)
            node_info.current_load["memory_usage"] = max(0, node_info.current_load["memory_usage"] - memory_needed)

    def _schedule_tasks(self):
        if not self.pending_tasks:
            return

        available_nodes = self.get_available_nodes()
        for node_info in available_nodes:
            if self.pending_tasks:
                self.get_task_for_node(node_info.node_id)

    def _reassign_tasks(self, node_id: str):
        if node_id not in self.assigned_tasks:
            return

        for task_id in self.assigned_tasks[node_id]:
            task = self.tasks.get(task_id)
            if task and task.status == "assigned":
                task.status = "pending"
                task.assigned_node = None
                task.assigned_at = None
                self.pending_tasks.append(task_id)

        del self.assigned_tasks[node_id]


class AdvancedScheduler(SimpleScheduler):
    """
    高级调度器

    支持多种调度策略：
    - FIFO: 先进先出
    - FAIR: 公平调度
    - PRIORITY: 优先级调度
    - DRF: 主导资源公平调度
    """

    def __init__(self, policy: SchedulingPolicy = SchedulingPolicy.DRF):
        super().__init__()
        self.policy = policy
        self.user_task_counts: dict[str, int] = defaultdict(int)
        self.user_resource_usage: dict[str, dict[str, float]] = defaultdict(lambda: {"cpu": 0.0, "memory": 0})
        self.total_resources: dict[str, float] = {"cpu": 0.0, "memory": 0}

    def register_node(self, node: NodeInfo) -> bool:
        result = super().register_node(node)
        if result:
            capacity = node.capacity
            self.total_resources["cpu"] += capacity.get("cpu", 0)
            self.total_resources["memory"] += capacity.get("memory", 0)
        return result

    def add_task(self, task: TaskInfo) -> str:
        task_id = super().add_task(task)
        if task.user_id:
            self.user_task_counts[task.user_id] += 1
        return task_id

    def get_task_for_node(self, node_id: str) -> Optional[TaskInfo]:
        if self.policy == SchedulingPolicy.FIFO:
            return self._fifo_schedule(node_id)
        elif self.policy == SchedulingPolicy.FAIR:
            return self._fair_schedule(node_id)
        elif self.policy == SchedulingPolicy.PRIORITY:
            return self._priority_schedule(node_id)
        elif self.policy == SchedulingPolicy.DRF:
            return self._drf_schedule(node_id)
        else:
            return super().get_task_for_node(node_id)

    def _fifo_schedule(self, node_id: str) -> Optional[TaskInfo]:
        with self.lock:
            if node_id not in self.nodes:
                return None

            node_info = self.nodes[node_id]

            if not self._is_node_available(node_id):
                return None

            for task_id in list(self.pending_tasks):
                task = self.tasks.get(task_id)
                if task and task.status == "pending" and self._evaluate_predicates(task, node_info):
                    self._assign_task(task, node_id)
                    return task

            return None

    def _fair_schedule(self, node_id: str) -> Optional[TaskInfo]:
        with self.lock:
            if node_id not in self.nodes:
                return None

            node_info = self.nodes[node_id]

            if not self._is_node_available(node_id):
                return None

            user_queues: dict[str, list[TaskInfo]] = defaultdict(list)

            for task_id in self.pending_tasks:
                task = self.tasks.get(task_id)
                if task and task.status == "pending":
                    user_id = task.user_id or "default"
                    user_queues[user_id].append(task)

            sorted_users = sorted(
                user_queues.keys(),
                key=lambda u: self.user_task_counts.get(u, 0)
            )

            for user_id in sorted_users:
                for task in user_queues[user_id]:
                    if self._evaluate_predicates(task, node_info):
                        self._assign_task(task, node_id)
                        return task

            return None

    def _priority_schedule(self, node_id: str) -> Optional[TaskInfo]:
        with self.lock:
            if node_id not in self.nodes:
                return None

            node_info = self.nodes[node_id]

            if not self._is_node_available(node_id):
                return None

            sorted_tasks = sorted(
                [self.tasks.get(tid) for tid in self.pending_tasks],
                key=lambda t: t.priority if t else -1,
                reverse=True
            )

            for task in sorted_tasks:
                if task and task.status == "pending" and self._evaluate_predicates(task, node_info):
                    self._assign_task(task, node_id)
                    return task

            return None

    def _drf_schedule(self, node_id: str) -> Optional[TaskInfo]:
        with self.lock:
            if node_id not in self.nodes:
                return None

            node_info = self.nodes[node_id]

            if not self._is_node_available(node_id):
                return None

            best_task = None
            best_drf_score = float('inf')

            for task_id in self.pending_tasks:
                task = self.tasks.get(task_id)
                if not task or task.status != "pending":
                    continue

                if not self._evaluate_predicates(task, node_info):
                    continue

                drf_score = self._calculate_drf_score(task)

                if drf_score < best_drf_score:
                    best_drf_score = drf_score
                    best_task = task

            if best_task:
                self._assign_task(best_task, node_id)
                self._update_drf_usage(best_task)
                return best_task

            return None

    def _calculate_drf_score(self, task: TaskInfo) -> float:
        user_id = task.user_id or "default"
        user_usage = self.user_resource_usage[user_id]

        cpu_share = user_usage["cpu"] / max(1.0, self.total_resources["cpu"])
        memory_share = user_usage["memory"] / max(1.0, self.total_resources["memory"])

        return max(cpu_share, memory_share)

    def _update_drf_usage(self, task: TaskInfo):
        user_id = task.user_id or "default"
        resources = task.required_resources

        self.user_resource_usage[user_id]["cpu"] += resources.get("cpu", 1.0)
        self.user_resource_usage[user_id]["memory"] += resources.get("memory", 512)

    def _assign_task(self, task: TaskInfo, node_id: str):
        task.status = "assigned"
        task.assigned_node = node_id
        task.assigned_at = time.time()
        self.pending_tasks.remove(str(task.task_id))
        self.assigned_tasks[node_id].append(str(task.task_id))
        self._update_node_load(node_id, task, "add")
        self.stats["tasks_processed"] += 1


__all__ = [
    "SchedulingPolicy",
    "TaskInfo",
    "NodeInfo",
    "Predicate",
    "ResourcePredicate",
    "TagPredicate",
    "PriorityPlugin",
    "ResourceBalancePlugin",
    "BaseScheduler",
    "SimpleScheduler",
    "AdvancedScheduler",
]

"""
Advanced Scheduler Module - Kubernetes-style Task Scheduling.

Implements:
- Predicate functions for node filtering
- Priority functions for node scoring
- Multiple scheduling policies (RoundRobin, LeastLoaded, BinPacking)
- Preemption for high-priority tasks
- Affinity/Anti-affinity constraints
- Resource quotas and limits

References:
- Kubernetes Scheduler: https://kubernetes.io/docs/concepts/scheduling-eviction/
- Scheduling Framework: https://kubernetes.io/docs/concepts/scheduling-eviction/scheduling-framework/
- Borg: "Large-scale cluster management at Google with Borg" (Verma et al., 2015)
"""

import asyncio
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Optional


class TaskPriority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3
    SYSTEM = 4


class TaskState(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SCHEDULING = "scheduling"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PREEMPTED = "preempted"


class NodeState(Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    DRAINING = "draining"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class SchedulingPolicy(Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    MOST_LOADED = "most_loaded"
    BIN_PACKING = "bin_packing"
    SPREAD = "spread"
    RANDOM = "random"
    PRIORITY = "priority"


@dataclass
class ResourceSpec:
    cpu: float = 1.0
    memory: float = 512.0
    gpu: int = 0
    storage: float = 0.0
    network: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "cpu": self.cpu,
            "memory": self.memory,
            "gpu": self.gpu,
            "storage": self.storage,
            "network": self.network,
        }

    def fits(self, available: "ResourceSpec") -> bool:
        return (
            self.cpu <= available.cpu and
            self.memory <= available.memory and
            self.gpu <= available.gpu and
            self.storage <= available.storage
        )

    def __add__(self, other: "ResourceSpec") -> "ResourceSpec":
        return ResourceSpec(
            cpu=self.cpu + other.cpu,
            memory=self.memory + other.memory,
            gpu=self.gpu + other.gpu,
            storage=self.storage + other.storage,
            network=self.network + other.network,
        )

    def __sub__(self, other: "ResourceSpec") -> "ResourceSpec":
        return ResourceSpec(
            cpu=max(0, self.cpu - other.cpu),
            memory=max(0, self.memory - other.memory),
            gpu=max(0, self.gpu - other.gpu),
            storage=max(0, self.storage - other.storage),
            network=max(0, self.network - other.network),
        )


@dataclass
class AffinitySpec:
    node_labels: dict[str, str] = field(default_factory=dict)
    node_affinity: list[str] = field(default_factory=list)
    node_anti_affinity: list[str] = field(default_factory=list)
    task_affinity: list[str] = field(default_factory=list)
    task_anti_affinity: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_labels": self.node_labels,
            "node_affinity": self.node_affinity,
            "node_anti_affinity": self.node_anti_affinity,
            "task_affinity": self.task_affinity,
            "task_anti_affinity": self.task_anti_affinity,
        }


@dataclass
class TaskSpec:
    task_id: str
    name: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    state: TaskState = TaskState.PENDING
    resources: ResourceSpec = field(default_factory=ResourceSpec)
    affinity: AffinitySpec = field(default_factory=AffinitySpec)
    tolerations: list[str] = field(default_factory=list)
    timeout: float = 300.0
    max_retries: int = 3
    retry_count: int = 0
    created_at: float = field(default_factory=time.time)
    scheduled_at: Optional[float] = None
    assigned_node: Optional[str] = None
    preemption_policy: str = "PreemptLowerPriority"
    user_id: str = ""
    labels: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "priority": self.priority.value,
            "state": self.state.value,
            "resources": self.resources.to_dict(),
            "affinity": self.affinity.to_dict(),
            "tolerations": self.tolerations,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "created_at": self.created_at,
            "scheduled_at": self.scheduled_at,
            "assigned_node": self.assigned_node,
            "user_id": self.user_id,
            "labels": self.labels,
        }


@dataclass
class NodeSpec:
    node_id: str
    name: str = ""
    state: NodeState = NodeState.AVAILABLE
    capacity: ResourceSpec = field(default_factory=ResourceSpec)
    allocated: ResourceSpec = field(default_factory=ResourceSpec)
    available: ResourceSpec = field(default_factory=ResourceSpec)
    labels: dict[str, str] = field(default_factory=dict)
    taints: list[str] = field(default_factory=list)
    tasks: set[str] = field(default_factory=set)
    last_heartbeat: float = field(default_factory=time.time)
    uptime: float = 0.0
    reliability_score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "state": self.state.value,
            "capacity": self.capacity.to_dict(),
            "allocated": self.allocated.to_dict(),
            "available": self.available.to_dict(),
            "labels": self.labels,
            "taints": self.taints,
            "tasks": list(self.tasks),
            "last_heartbeat": self.last_heartbeat,
            "uptime": self.uptime,
            "reliability_score": self.reliability_score,
        }

    def can_fit(self, resources: ResourceSpec) -> bool:
        return resources.fits(self.available)

    def allocate(self, resources: ResourceSpec) -> bool:
        if not self.can_fit(resources):
            return False

        self.allocated = self.allocated + resources
        self.available = self.available - resources
        return True

    def deallocate(self, resources: ResourceSpec) -> None:
        self.allocated = self.allocated - resources
        self.available = self.available + resources

        self.allocated = ResourceSpec(
            cpu=max(0, self.allocated.cpu),
            memory=max(0, self.allocated.memory),
            gpu=max(0, self.allocated.gpu),
            storage=max(0, self.allocated.storage),
        )


class Predicate(ABC):
    """Base class for scheduling predicates."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def check(self, node: NodeSpec, task: TaskSpec) -> bool:
        pass


class ResourceFitPredicate(Predicate):
    """Check if node has enough resources."""

    @property
    def name(self) -> str:
        return "ResourceFit"

    def check(self, node: NodeSpec, task: TaskSpec) -> bool:
        return node.can_fit(task.resources)


class NodeStatePredicate(Predicate):
    """Check if node is available for scheduling."""

    @property
    def name(self) -> str:
        return "NodeState"

    def check(self, node: NodeSpec, task: TaskSpec) -> bool:
        return node.state == NodeState.AVAILABLE


class NodeAffinityPredicate(Predicate):
    """Check node affinity constraints."""

    @property
    def name(self) -> str:
        return "NodeAffinity"

    def check(self, node: NodeSpec, task: TaskSpec) -> bool:
        if not task.affinity.node_labels:
            return True

        for key, value in task.affinity.node_labels.items():
            if node.labels.get(key) != value:
                return False

        return True


class TaintTolerationPredicate(Predicate):
    """Check if task tolerates node taints."""

    @property
    def name(self) -> str:
        return "TaintToleration"

    def check(self, node: NodeSpec, task: TaskSpec) -> bool:
        if not node.taints:
            return True

        return all(taint in task.tolerations for taint in node.taints)


class TaskAntiAffinityPredicate(Predicate):
    """Check task anti-affinity constraints."""

    @property
    def name(self) -> str:
        return "TaskAntiAffinity"

    def check(self, node: NodeSpec, task: TaskSpec) -> bool:
        if not task.affinity.task_anti_affinity:
            return True

        for anti_task_id in task.affinity.task_anti_affinity:
            if anti_task_id in node.tasks:
                return False

        return True


class PriorityFunction(ABC):
    """Base class for scheduling priority functions."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def score(self, node: NodeSpec, task: TaskSpec) -> float:
        pass


class ResourceBalancePriority(PriorityFunction):
    """Score based on resource balance after scheduling."""

    @property
    def name(self) -> str:
        return "ResourceBalance"

    def score(self, node: NodeSpec, task: TaskSpec) -> float:
        remaining = node.available - task.resources

        cpu_score = remaining.cpu / max(node.capacity.cpu, 0.1)
        memory_score = remaining.memory / max(node.capacity.memory, 1)

        balance = (cpu_score + memory_score) / 2

        return balance * 100


class LeastLoadedPriority(PriorityFunction):
    """Score higher for less loaded nodes."""

    @property
    def name(self) -> str:
        return "LeastLoaded"

    def score(self, node: NodeSpec, task: TaskSpec) -> float:
        cpu_usage = node.allocated.cpu / max(node.capacity.cpu, 0.1)
        memory_usage = node.allocated.memory / max(node.capacity.memory, 1)

        avg_usage = (cpu_usage + memory_usage) / 2

        return (1 - avg_usage) * 100


class MostLoadedPriority(PriorityFunction):
    """Score higher for more loaded nodes (bin packing)."""

    @property
    def name(self) -> str:
        return "MostLoaded"

    def score(self, node: NodeSpec, task: TaskSpec) -> float:
        cpu_usage = node.allocated.cpu / max(node.capacity.cpu, 0.1)
        memory_usage = node.allocated.memory / max(node.capacity.memory, 1)

        avg_usage = (cpu_usage + memory_usage) / 2

        return avg_usage * 100


class NodeReliabilityPriority(PriorityFunction):
    """Score based on node reliability."""

    @property
    def name(self) -> str:
        return "NodeReliability"

    def score(self, node: NodeSpec, task: TaskSpec) -> float:
        return node.reliability_score * 100


class SpreadPriority(PriorityFunction):
    """Score to spread tasks across nodes."""

    @property
    def name(self) -> str:
        return "Spread"

    def score(self, node: NodeSpec, task: TaskSpec) -> float:
        task_count = len(node.tasks)

        return 100 / (task_count + 1)


class Scheduler:
    """Advanced task scheduler with Kubernetes-style algorithms.

    Implements:
    - Predicate-based node filtering
    - Priority-based node scoring
    - Multiple scheduling policies
    - Preemption for high-priority tasks
    """

    DEFAULT_PREDICATES = [
        ResourceFitPredicate(),
        NodeStatePredicate(),
        NodeAffinityPredicate(),
        TaintTolerationPredicate(),
        TaskAntiAffinityPredicate(),
    ]

    DEFAULT_PRIORITIES = [
        (ResourceBalancePriority(), 1.0),
        (LeastLoadedPriority(), 0.5),
        (NodeReliabilityPriority(), 0.3),
    ]

    def __init__(
        self,
        policy: SchedulingPolicy = SchedulingPolicy.LEAST_LOADED,
        predicates: list[Predicate] = None,
        priorities: list[tuple[PriorityFunction, float]] = None,
    ):
        self.policy = policy
        self.predicates = predicates or self.DEFAULT_PREDICATES
        self.priorities = priorities or self.DEFAULT_PRIORITIES

        self._nodes: dict[str, NodeSpec] = {}
        self._tasks: dict[str, TaskSpec] = {}
        self._queue: list[str] = []
        self._round_robin_index = 0
        self._scheduling_lock = asyncio.Lock()

        self._stats = {
            "scheduled": 0,
            "failed": 0,
            "preemptions": 0,
        }

    def add_node(self, node: NodeSpec) -> None:
        self._nodes[node.node_id] = node
        node.available = node.capacity

    def remove_node(self, node_id: str) -> None:
        if node_id in self._nodes:
            del self._nodes[node_id]

    def update_node(self, node: NodeSpec) -> None:
        self._nodes[node.node_id] = node

    def get_node(self, node_id: str) -> Optional[NodeSpec]:
        return self._nodes.get(node_id)

    def list_nodes(self) -> list[NodeSpec]:
        return list(self._nodes.values())

    def submit_task(self, task: TaskSpec) -> None:
        self._tasks[task.task_id] = task
        self._queue.append(task.task_id)
        task.state = TaskState.QUEUED

    def cancel_task(self, task_id: str) -> bool:
        if task_id in self._queue:
            self._queue.remove(task_id)

        if task_id in self._tasks:
            task = self._tasks[task_id]
            if task.assigned_node:
                node = self._nodes.get(task.assigned_node)
                if node:
                    node.deallocate(task.resources)
                    node.tasks.discard(task_id)
            del self._tasks[task_id]
            return True

        return False

    def get_task(self, task_id: str) -> Optional[TaskSpec]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[TaskSpec]:
        return list(self._tasks.values())

    def _filter_nodes(self, task: TaskSpec) -> list[NodeSpec]:
        """Filter nodes using predicates."""
        candidates = []

        for node in self._nodes.values():
            passes_all = True

            for predicate in self.predicates:
                if not predicate.check(node, task):
                    passes_all = False
                    break

            if passes_all:
                candidates.append(node)

        return candidates

    def _score_nodes(
        self,
        nodes: list[NodeSpec],
        task: TaskSpec
    ) -> list[tuple[NodeSpec, float]]:
        """Score nodes using priority functions."""
        scored = []

        for node in nodes:
            total_score = 0.0

            for priority_func, weight in self.priorities:
                score = priority_func.score(node, task)
                total_score += score * weight

            scored.append((node, total_score))

        return sorted(scored, key=lambda x: x[1], reverse=True)

    def _select_node_policy(
        self,
        candidates: list[NodeSpec],
        task: TaskSpec
    ) -> Optional[NodeSpec]:
        """Select node based on scheduling policy."""
        if not candidates:
            return None

        if self.policy == SchedulingPolicy.RANDOM:
            return random.choice(candidates)

        elif self.policy == SchedulingPolicy.ROUND_ROBIN:
            node = candidates[self._round_robin_index % len(candidates)]
            self._round_robin_index += 1
            return node

        elif self.policy == SchedulingPolicy.LEAST_LOADED:
            scored = self._score_nodes(candidates, task)
            return scored[0][0] if scored else None

        elif self.policy in (SchedulingPolicy.MOST_LOADED, SchedulingPolicy.BIN_PACKING):
            priorities = [(MostLoadedPriority(), 1.0)]
            scored = []
            for node in candidates:
                total = sum(p.score(node, task) * w for p, w in priorities)
                scored.append((node, total))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[0][0] if scored else None

        elif self.policy == SchedulingPolicy.SPREAD:
            priorities = [(SpreadPriority(), 1.0)]
            scored = []
            for node in candidates:
                total = sum(p.score(node, task) * w for p, w in priorities)
                scored.append((node, total))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[0][0] if scored else None

        elif self.policy == SchedulingPolicy.PRIORITY:
            scored = self._score_nodes(candidates, task)
            return scored[0][0] if scored else None

        return candidates[0]

    def _find_preemption_candidates(
        self,
        task: TaskSpec
    ) -> list[tuple[NodeSpec, list[TaskSpec]]]:
        """Find nodes where lower priority tasks can be preempted."""
        candidates = []

        for node in self._nodes.values():
            if node.state != NodeState.AVAILABLE:
                continue

            lower_priority_tasks = []
            for task_id in node.tasks:
                running_task = self._tasks.get(task_id)
                if running_task and running_task.priority < task.priority:
                    lower_priority_tasks.append(running_task)

            if lower_priority_tasks:
                preemptable = sorted(
                    lower_priority_tasks,
                    key=lambda t: t.priority
                )

                freed_resources = ResourceSpec()
                needed = task.resources

                for pt in preemptable:
                    freed_resources = freed_resources + pt.resources
                    if needed.fits(freed_resources):
                        candidates.append((node, preemptable))
                        break

        return candidates

    def _preempt_tasks(
        self,
        node: NodeSpec,
        tasks_to_preempt: list[TaskSpec],
        new_task: TaskSpec
    ) -> bool:
        """Preempt lower priority tasks to make room for new task."""
        for task in tasks_to_preempt:
            task.state = TaskState.PREEMPTED
            task.assigned_node = None
            node.deallocate(task.resources)
            node.tasks.discard(task.task_id)

            self._stats["preemptions"] += 1

        return node.allocate(new_task.resources)

    async def schedule(self) -> list[tuple[str, Optional[str]]]:
        """Schedule all pending tasks.

        Returns:
            List of (task_id, assigned_node) tuples
        """
        async with self._scheduling_lock:
            results = []

            sorted_queue = sorted(
                self._queue,
                key=lambda tid: self._tasks[tid].priority,
                reverse=True
            )

            for task_id in sorted_queue[:]:
                task = self._tasks.get(task_id)
                if not task:
                    continue

                task.state = TaskState.SCHEDULING

                candidates = self._filter_nodes(task)

                if candidates:
                    selected = self._select_node_policy(candidates, task)

                    if selected and selected.allocate(task.resources):
                        selected.tasks.add(task.task_id)
                        task.assigned_node = selected.node_id
                        task.scheduled_at = time.time()
                        task.state = TaskState.ASSIGNED

                        self._queue.remove(task_id)
                        self._stats["scheduled"] += 1
                        results.append((task_id, selected.node_id))
                        continue

                if task.priority >= TaskPriority.HIGH:
                    preemption_candidates = self._find_preemption_candidates(task)

                    if preemption_candidates:
                        node, tasks_to_preempt = preemption_candidates[0]

                        if self._preempt_tasks(node, tasks_to_preempt, task):
                            node.tasks.add(task.task_id)
                            task.assigned_node = node.node_id
                            task.scheduled_at = time.time()
                            task.state = TaskState.ASSIGNED

                            self._queue.remove(task_id)
                            self._stats["scheduled"] += 1
                            results.append((task_id, node.node_id))
                            continue

                task.state = TaskState.PENDING
                self._stats["failed"] += 1
                results.append((task_id, None))

            return results

    def complete_task(self, task_id: str, success: bool = True) -> None:
        """Mark task as completed and release resources."""
        task = self._tasks.get(task_id)
        if not task:
            return

        node = self._nodes.get(task.assigned_node) if task.assigned_node else None

        if node:
            node.deallocate(task.resources)
            node.tasks.discard(task_id)

        task.state = TaskState.COMPLETED if success else TaskState.FAILED

    def get_stats(self) -> dict[str, Any]:
        """Get scheduler statistics."""
        return {
            "policy": self.policy.value,
            "total_nodes": len(self._nodes),
            "available_nodes": sum(1 for n in self._nodes.values() if n.state == NodeState.AVAILABLE),
            "total_tasks": len(self._tasks),
            "queued_tasks": len(self._queue),
            "scheduled": self._stats["scheduled"],
            "failed": self._stats["failed"],
            "preemptions": self._stats["preemptions"],
        }

    def get_cluster_resources(self) -> dict[str, Any]:
        """Get cluster-wide resource statistics."""
        total_capacity = ResourceSpec(cpu=0.0, memory=0.0, gpu=0, storage=0.0, network=0.0)
        total_allocated = ResourceSpec(cpu=0.0, memory=0.0, gpu=0, storage=0.0, network=0.0)
        total_available = ResourceSpec(cpu=0.0, memory=0.0, gpu=0, storage=0.0, network=0.0)

        for node in self._nodes.values():
            total_capacity = total_capacity + node.capacity
            total_allocated = total_allocated + node.allocated
            total_available = total_available + node.available

        return {
            "capacity": total_capacity.to_dict(),
            "allocated": total_allocated.to_dict(),
            "available": total_available.to_dict(),
            "utilization": {
                "cpu": total_allocated.cpu / max(total_capacity.cpu, 0.1) * 100,
                "memory": total_allocated.memory / max(total_capacity.memory, 1) * 100,
            },
        }


__all__ = [
    "TaskPriority",
    "TaskState",
    "NodeState",
    "SchedulingPolicy",
    "ResourceSpec",
    "AffinitySpec",
    "TaskSpec",
    "NodeSpec",
    "Predicate",
    "ResourceFitPredicate",
    "NodeStatePredicate",
    "NodeAffinityPredicate",
    "TaintTolerationPredicate",
    "TaskAntiAffinityPredicate",
    "PriorityFunction",
    "ResourceBalancePriority",
    "LeastLoadedPriority",
    "MostLoadedPriority",
    "NodeReliabilityPriority",
    "SpreadPriority",
    "Scheduler",
]

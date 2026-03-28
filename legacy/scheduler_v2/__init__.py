"""
Advanced Scheduler with Fair Scheduling and DRF Algorithm.

This module implements advanced scheduling algorithms inspired by:
- Kubernetes Scheduler (Predicate + Priority)
- Apache Mesos DRF (Dominant Resource Fairness)
- Ray Scheduler (Actor-based scheduling)

References:
- DRF Paper: https://cs.stanford.edu/~matei/papers/2011/nsdi_drf.pdf
- Kubernetes Scheduling: https://kubernetes.io/docs/concepts/scheduling-eviction/
"""
import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SchedulingPolicy(str, Enum):
    """Scheduling policy enumeration."""
    FIFO = "fifo"
    FAIR = "fair"
    PRIORITY = "priority"
    DRF = "drf"


@dataclass
class UserMetrics:
    """User resource consumption metrics."""
    user_id: str
    cpu_consumed: float = 0.0
    memory_consumed: float = 0.0
    tasks_completed: int = 0
    tasks_submitted: int = 0
    contribution_score: float = 0.0
    last_task_time: float = 0.0

    def dominant_share(self, total_cpu: float, total_memory: float) -> float:
        """Calculate dominant resource share for DRF."""
        if total_cpu <= 0 or total_memory <= 0:
            return 0.0

        cpu_share = self.cpu_consumed / total_cpu
        memory_share = self.memory_consumed / total_memory

        return max(cpu_share, memory_share)


@dataclass
class SchedulingContext:
    """Context for scheduling decision."""
    task_id: int
    user_id: Optional[str]
    resources: dict[str, float]
    priority: int = 0
    submitted_at: float = field(default_factory=time.time)
    wait_time: float = 0.0
    retry_count: int = 0


@dataclass
class NodeScore:
    """Node scoring result."""
    node_id: str
    score: float
    reasons: list[str] = field(default_factory=list)

    def __lt__(self, other):
        return self.score < other.score


class Predicate(ABC):
    """Abstract base class for scheduling predicates."""

    @abstractmethod
    def check(self, node: dict, task: dict) -> bool:
        """Check if node satisfies the predicate."""
        pass


class ResourceFitPredicate(Predicate):
    """Check if node has sufficient resources."""

    def check(self, node: dict, task: dict) -> bool:
        required = task.get("resources", {})
        available = node.get("available_resources", {})

        cpu_ok = available.get("cpu", 0) >= required.get("cpu", 0)
        memory_ok = available.get("memory", 0) >= required.get("memory", 0)

        return cpu_ok and memory_ok


class NodeAvailablePredicate(Predicate):
    """Check if node is available for scheduling."""

    def check(self, node: dict, task: dict) -> bool:
        return (
            node.get("is_available", False) and
            node.get("is_idle", False) and
            node.get("status") != "offline"
        )


class NodeSelectorPredicate(Predicate):
    """Check if node matches selector."""

    def __init__(self, selector: dict[str, Any]):
        self.selector = selector

    def check(self, node: dict, task: dict) -> bool:
        node_tags = node.get("tags", {})

        return all(node_tags.get(key) == value for key, value in self.selector.items())


class PriorityPlugin(ABC):
    """Abstract base class for priority plugins."""

    @abstractmethod
    def score(self, node: dict, task: dict) -> tuple[float, str]:
        """Calculate priority score for node-task pair."""
        pass


class ResourceBalancePriority(PriorityPlugin):
    """Prioritize nodes for resource balance."""

    def __init__(self, weight: float = 1.0):
        self.weight = weight

    def score(self, node: dict, task: dict) -> tuple[float, str]:
        required = task.get("resources", {})
        available = node.get("available_resources", {})
        node.get("capacity", {})

        cpu_score = 0.0
        if available.get("cpu", 0) >= required.get("cpu", 0):
            cpu_score = required.get("cpu", 0) / max(available.get("cpu", 0.1), 0.1)

        memory_score = 0.0
        if available.get("memory", 0) >= required.get("memory", 0):
            memory_score = required.get("memory", 0) / max(available.get("memory", 0.1), 0.1)

        score = (cpu_score + memory_score) / 2 * self.weight
        return score, f"Resource balance: {score:.2f}"


class LeastLoadedPriority(PriorityPlugin):
    """Prioritize least loaded nodes."""

    def __init__(self, weight: float = 1.0):
        self.weight = weight

    def score(self, node: dict, task: dict) -> tuple[float, str]:
        cpu_usage = node.get("cpu_usage", 0)
        memory_usage = node.get("memory_usage", 0)

        load_score = (100 - cpu_usage + 100 - memory_usage) / 200
        score = load_score * self.weight

        return score, f"Least loaded: {score:.2f}"


class AffinityPriority(PriorityPlugin):
    """Prioritize nodes based on affinity rules."""

    def __init__(self, weight: float = 1.0):
        self.weight = weight

    def score(self, node: dict, task: dict) -> tuple[float, str]:
        affinity = task.get("affinity", {})
        node_id = node.get("node_id", "")
        node_tags = node.get("tags", {})

        score = 0.0

        preferred = affinity.get("preferred_nodes", [])
        if node_id in preferred:
            score += 0.5

        tag_affinity = affinity.get("tag_affinity", {})
        for key, value in tag_affinity.items():
            if node_tags.get(key) == value:
                score += 0.25

        score = min(score, 1.0) * self.weight
        return score, f"Affinity: {score:.2f}"


class DRFPriority(PriorityPlugin):
    """
    Dominant Resource Fairness priority plugin.

    Reference: "Fair Allocation of Multiple Resource Types"
    https://cs.stanford.edu/~matei/papers/2011/nsdi_drf.pdf
    """

    def __init__(
        self,
        weight: float = 1.0,
        user_metrics: dict[str, UserMetrics] = None,
        total_cpu: float = 100.0,
        total_memory: float = 100000.0
    ):
        self.weight = weight
        self.user_metrics = user_metrics or {}
        self.total_cpu = total_cpu
        self.total_memory = total_memory

    def score(self, node: dict, task: dict) -> tuple[float, str]:
        user_id = task.get("user_id")

        if not user_id or user_id not in self.user_metrics:
            return self.weight, "DRF: New user bonus"

        user = self.user_metrics[user_id]
        dominant_share = user.dominant_share(self.total_cpu, self.total_memory)

        score = (1.0 - dominant_share) * self.weight
        return score, f"DRF: {score:.2f} (share: {dominant_share:.2f})"


class AdvancedScheduler:
    """
    Advanced scheduler with multiple scheduling policies.

    Features:
    - Two-phase scheduling (Predicate + Priority)
    - Multiple scheduling policies (FIFO, Fair, Priority, DRF)
    - Anti-starvation mechanism
    - Configurable predicates and priorities

    Usage:
        scheduler = AdvancedScheduler(policy=SchedulingPolicy.DRF)

        # Register predicates
        scheduler.add_predicate(ResourceFitPredicate())
        scheduler.add_predicate(NodeAvailablePredicate())

        # Register priorities
        scheduler.add_priority(ResourceBalancePriority(weight=0.4))
        scheduler.add_priority(LeastLoadedPriority(weight=0.3))
        scheduler.add_priority(DRFPriority(weight=0.3))

        # Schedule task
        node_id = scheduler.schedule(task, nodes)
    """

    def __init__(
        self,
        policy: SchedulingPolicy = SchedulingPolicy.FAIR,
        starvation_threshold: float = 300.0,
        newcomer_bonus: int = 10
    ):
        self.policy = policy
        self.starvation_threshold = starvation_threshold
        self.newcomer_bonus = newcomer_bonus

        self.predicates: list[Predicate] = []
        self.priorities: list[PriorityPlugin] = []

        self.user_metrics: dict[str, UserMetrics] = {}
        self.total_cpu: float = 0.0
        self.total_memory: float = 0.0

        self._lock = asyncio.Lock()

    def add_predicate(self, predicate: Predicate):
        """Add a scheduling predicate."""
        self.predicates.append(predicate)

    def add_priority(self, priority: PriorityPlugin):
        """Add a priority plugin."""
        self.priorities.append(priority)

    def update_cluster_resources(self, nodes: list[dict]):
        """Update total cluster resources."""
        self.total_cpu = sum(n.get("capacity", {}).get("cpu", 0) for n in nodes)
        self.total_memory = sum(n.get("capacity", {}).get("memory", 0) for n in nodes)

    def _filter_nodes(self, task: dict, nodes: list[dict]) -> list[dict]:
        """Filter nodes using predicates."""
        feasible = []

        for node in nodes:
            passes_all = True

            for predicate in self.predicates:
                if not predicate.check(node, task):
                    passes_all = False
                    break

            if passes_all:
                feasible.append(node)

        return feasible

    def _score_nodes(self, task: dict, nodes: list[dict]) -> list[NodeScore]:
        """Score nodes using priority plugins."""
        scores = []

        for node in nodes:
            total_score = 0.0
            reasons = []

            for priority in self.priorities:
                score, reason = priority.score(node, task)
                total_score += score
                reasons.append(reason)

            wait_time = time.time() - task.get("submitted_at", time.time())
            if wait_time > self.starvation_threshold:
                bonus = min(wait_time / 60, 10)
                total_score += bonus
                reasons.append(f"Anti-starvation bonus: {bonus:.2f}")

            user_id = task.get("user_id")
            if user_id:
                user = self.user_metrics.get(user_id)
                if user and user.tasks_submitted <= self.newcomer_bonus:
                    total_score += 0.5
                    reasons.append("Newcomer bonus: 0.5")

            scores.append(NodeScore(
                node_id=node.get("node_id", ""),
                score=total_score,
                reasons=reasons
            ))

        return scores

    def schedule(
        self,
        task: dict,
        nodes: list[dict]
    ) -> Optional[str]:
        """
        Schedule a task to a node.

        Args:
            task: Task to schedule
            nodes: Available nodes

        Returns:
            Selected node ID or None if no suitable node
        """
        feasible_nodes = self._filter_nodes(task, nodes)

        if not feasible_nodes:
            return None

        scores = self._score_nodes(task, feasible_nodes)

        if not scores:
            return None

        scores.sort(reverse=True)
        best = scores[0]

        return best.node_id

    def record_task_submission(self, user_id: str, resources: dict):
        """Record task submission for fair scheduling."""
        if user_id not in self.user_metrics:
            self.user_metrics[user_id] = UserMetrics(user_id=user_id)

        user = self.user_metrics[user_id]
        user.tasks_submitted += 1
        user.cpu_consumed += resources.get("cpu", 0)
        user.memory_consumed += resources.get("memory", 0)

    def record_task_completion(
        self,
        user_id: str,
        success: bool,
        contribution: float = 0.0
    ):
        """Record task completion for fair scheduling."""
        if user_id not in self.user_metrics:
            return

        user = self.user_metrics[user_id]

        if success:
            user.tasks_completed += 1
            user.contribution_score += contribution

        user.last_task_time = time.time()

    def get_user_metrics(self, user_id: str) -> Optional[UserMetrics]:
        """Get metrics for a user."""
        return self.user_metrics.get(user_id)

    def get_scheduling_stats(self) -> dict[str, Any]:
        """Get scheduling statistics."""
        return {
            "policy": self.policy.value,
            "total_users": len(self.user_metrics),
            "total_cluster_cpu": self.total_cpu,
            "total_cluster_memory": self.total_memory,
            "predicate_count": len(self.predicates),
            "priority_count": len(self.priorities),
            "user_stats": {
                user_id: {
                    "tasks_submitted": user.tasks_submitted,
                    "tasks_completed": user.tasks_completed,
                    "contribution_score": user.contribution_score,
                    "dominant_share": user.dominant_share(self.total_cpu, self.total_memory)
                }
                for user_id, user in self.user_metrics.items()
            }
        }


def create_default_scheduler(
    policy: SchedulingPolicy = SchedulingPolicy.FAIR,
    user_metrics: dict[str, UserMetrics] = None,
    total_cpu: float = 100.0,
    total_memory: float = 100000.0
) -> AdvancedScheduler:
    """
    Create a scheduler with default configuration.

    Includes:
    - ResourceFitPredicate
    - NodeAvailablePredicate
    - ResourceBalancePriority
    - LeastLoadedPriority
    - DRFPriority
    """
    scheduler = AdvancedScheduler(policy=policy)

    scheduler.add_predicate(ResourceFitPredicate())
    scheduler.add_predicate(NodeAvailablePredicate())

    scheduler.add_priority(ResourceBalancePriority(weight=0.35))
    scheduler.add_priority(LeastLoadedPriority(weight=0.25))
    scheduler.add_priority(AffinityPriority(weight=0.15))
    scheduler.add_priority(DRFPriority(
        weight=0.25,
        user_metrics=user_metrics,
        total_cpu=total_cpu,
        total_memory=total_memory
    ))

    return scheduler

"""Task Dependency Resolver - Resolves and validates task dependencies."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class DependencyType(str, Enum):
    HARD = "hard"
    SOFT = "soft"
    CONDITIONAL = "conditional"


class DependencyStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    FAILED = "failed"
    CYCLIC = "cyclic"


@dataclass
class Dependency(Generic[T]):
    source: T
    target: T
    dep_type: DependencyType = DependencyType.HARD
    condition: Callable[[Any], bool] | None = None
    description: str = ""


@dataclass
class DependencyNode(Generic[T]):
    id: T
    dependencies: set[T] = field(default_factory=set)
    dependents: set[T] = field(default_factory=set)
    soft_dependencies: set[T] = field(default_factory=set)
    conditional_dependencies: dict[T, Callable] = field(default_factory=dict)
    level: int = 0
    visited: bool = False
    in_stack: bool = False


@dataclass
class ResolutionResult(Generic[T]):
    success: bool
    execution_order: list[T] = field(default_factory=list)
    levels: dict[T, int] = field(default_factory=dict)
    cycles: list[list[T]] = field(default_factory=list)
    unresolved: list[T] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class DependencyGraph(Generic[T]):
    def __init__(self):
        self.nodes: dict[T, DependencyNode[T]] = {}
        self.edges: list[Dependency[T]] = []

    def add_node(self, node_id: T) -> DependencyNode[T]:
        if node_id not in self.nodes:
            self.nodes[node_id] = DependencyNode(id=node_id)
        return self.nodes[node_id]

    def add_dependency(
        self,
        source: T,
        target: T,
        dep_type: DependencyType = DependencyType.HARD,
        condition: Callable | None = None
    ) -> Dependency[T]:
        source_node = self.add_node(source)
        target_node = self.add_node(target)

        dep = Dependency(
            source=source,
            target=target,
            dep_type=dep_type,
            condition=condition
        )
        self.edges.append(dep)

        if dep_type == DependencyType.HARD:
            source_node.dependencies.add(target)
            target_node.dependents.add(source)
        elif dep_type == DependencyType.SOFT:
            source_node.soft_dependencies.add(target)
        elif dep_type == DependencyType.CONDITIONAL and condition:
            source_node.conditional_dependencies[target] = condition

        return dep

    def remove_dependency(self, source: T, target: T) -> bool:
        if source not in self.nodes or target not in self.nodes:
            return False

        source_node = self.nodes[source]
        target_node = self.nodes[target]

        source_node.dependencies.discard(target)
        source_node.soft_dependencies.discard(target)
        source_node.conditional_dependencies.pop(target, None)
        target_node.dependents.discard(source)

        self.edges = [
            e for e in self.edges
            if not (e.source == source and e.target == target)
        ]

        return True

    def remove_node(self, node_id: T) -> bool:
        if node_id not in self.nodes:
            return False

        node = self.nodes[node_id]

        for dep_id in list(node.dependencies):
            if dep_id in self.nodes:
                self.nodes[dep_id].dependents.discard(node_id)

        for dep_id in list(node.dependents):
            if dep_id in self.nodes:
                self.nodes[dep_id].dependencies.discard(node_id)

        for dep_id in list(node.soft_dependencies):
            if dep_id in self.nodes:
                self.nodes[dep_id].dependents.discard(node_id)

        del self.nodes[node_id]

        self.edges = [
            e for e in self.edges
            if e.source != node_id and e.target != node_id
        ]

        return True

    def get_dependencies(self, node_id: T, include_soft: bool = False) -> set[T]:
        if node_id not in self.nodes:
            return set()

        node = self.nodes[node_id]
        deps = set(node.dependencies)

        if include_soft:
            deps.update(node.soft_dependencies)

        return deps

    def get_dependents(self, node_id: T) -> set[T]:
        if node_id not in self.nodes:
            return set()
        return set(self.nodes[node_id].dependents)

    def detect_cycles(self) -> list[list[T]]:
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node_id: T, path: list[T]) -> list[T] | None:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            for dep_id in self.nodes[node_id].dependencies:
                if dep_id not in visited:
                    result = dfs(dep_id, path)
                    if result:
                        return result
                elif dep_id in rec_stack:
                    cycle_start = path.index(dep_id)
                    return path[cycle_start:]

            path.pop()
            rec_stack.remove(node_id)
            return None

        for node_id in self.nodes:
            if node_id not in visited:
                cycle = dfs(node_id, [])
                if cycle:
                    cycles.append(cycle)

        return cycles

    def has_cycle(self) -> bool:
        return len(self.detect_cycles()) > 0

    def topological_sort(self) -> list[T]:
        in_degree = defaultdict(int)

        for node_id in self.nodes:
            in_degree[node_id]
            for _dep_id in self.nodes[node_id].dependencies:
                in_degree[node_id] += 1

        queue = deque([
            node_id for node_id in self.nodes
            if in_degree[node_id] == 0
        ])

        result = []

        while queue:
            node_id = queue.popleft()
            result.append(node_id)

            for dependent_id in self.nodes[node_id].dependents:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)

        if len(result) != len(self.nodes):
            return []

        return result

    def compute_levels(self) -> dict[T, int]:
        levels = {}

        def compute_level(node_id: T) -> int:
            if node_id in levels:
                return levels[node_id]

            node = self.nodes[node_id]
            if not node.dependencies:
                levels[node_id] = 0
                return 0

            max_dep_level = max(
                compute_level(dep_id)
                for dep_id in node.dependencies
            )

            levels[node_id] = max_dep_level + 1
            return levels[node_id]

        for node_id in self.nodes:
            compute_level(node_id)

        return levels

    def get_execution_groups(self) -> list[list[T]]:
        levels = self.compute_levels()

        groups = defaultdict(list)
        for node_id, level in levels.items():
            groups[level].append(node_id)

        return [groups[i] for i in sorted(groups.keys())]

    def get_critical_path(self) -> list[T]:
        levels = self.compute_levels()
        if not levels:
            return []

        max_level = max(levels.values())
        path = []
        current_level = max_level

        candidates = [
            node_id for node_id, level in levels.items()
            if level == current_level
        ]

        while candidates and current_level >= 0:
            path.append(candidates[0])
            current_level -= 1

            candidates = [
                dep_id for dep_id in self.nodes[candidates[0]].dependencies
                if levels.get(dep_id) == current_level
            ]

        return list(reversed(path))

    def subgraph(self, node_ids: set[T]) -> DependencyGraph[T]:
        sub = DependencyGraph[T]()

        for node_id in node_ids:
            if node_id in self.nodes:
                sub.add_node(node_id)

        for edge in self.edges:
            if edge.source in node_ids and edge.target in node_ids:
                sub.add_dependency(
                    edge.source,
                    edge.target,
                    edge.dep_type,
                    edge.condition
                )

        return sub

    def ancestors(self, node_id: T) -> set[T]:
        if node_id not in self.nodes:
            return set()

        ancestors = set()
        queue = deque(self.nodes[node_id].dependencies)

        while queue:
            dep_id = queue.popleft()
            if dep_id not in ancestors:
                ancestors.add(dep_id)
                queue.extend(self.nodes[dep_id].dependencies)

        return ancestors

    def descendants(self, node_id: T) -> set[T]:
        if node_id not in self.nodes:
            return set()

        descendants = set()
        queue = deque(self.nodes[node_id].dependents)

        while queue:
            dep_id = queue.popleft()
            if dep_id not in descendants:
                descendants.add(dep_id)
                queue.extend(self.nodes[dep_id].dependents)

        return descendants


class DependencyResolver(Generic[T]):
    def __init__(self, graph: DependencyGraph[T] | None = None):
        self.graph = graph or DependencyGraph[T]()

    def add_task(self, task_id: T, dependencies: list[T] | None = None):
        self.graph.add_node(task_id)

        if dependencies:
            for dep_id in dependencies:
                self.graph.add_dependency(task_id, dep_id)

    def resolve(self) -> ResolutionResult[T]:
        result = ResolutionResult[T](success=True)

        cycles = self.graph.detect_cycles()
        if cycles:
            result.success = False
            result.cycles = cycles
            result.errors.append(f"Detected {len(cycles)} cycle(s) in dependency graph")
            return result

        result.execution_order = self.graph.topological_sort()
        result.levels = self.graph.compute_levels()

        if not result.execution_order:
            result.success = False
            result.errors.append("Failed to generate execution order")

        return result

    def can_execute(self, task_id: T, completed: set[T]) -> bool:
        if task_id not in self.graph.nodes:
            return True

        node = self.graph.nodes[task_id]

        return all(dep_id in completed for dep_id in node.dependencies)

    def get_ready_tasks(self, completed: set[T], running: set[T]) -> list[T]:
        ready = []

        for node_id, _node in self.graph.nodes.items():
            if node_id in completed or node_id in running:
                continue

            if self.can_execute(node_id, completed):
                ready.append(node_id)

        return ready

    def get_blocked_tasks(self, failed: set[T]) -> set[T]:
        blocked = set()

        for node_id, node in self.graph.nodes.items():
            if node_id in failed:
                continue

            for dep_id in node.dependencies:
                if dep_id in failed:
                    blocked.add(node_id)
                    break

        return blocked

    def get_parallelism_level(self) -> int:
        groups = self.graph.get_execution_groups()
        return max(len(g) for g in groups) if groups else 0


class TaskDependencyManager:
    def __init__(self):
        self.graph = DependencyGraph[str]()
        self.resolver = DependencyResolver(self.graph)
        self._task_data: dict[str, Any] = {}

    def register_task(
        self,
        task_id: str,
        dependencies: list[str] | None = None,
        data: Any | None = None
    ):
        self.graph.add_node(task_id)
        self._task_data[task_id] = data

        if dependencies:
            for dep_id in dependencies:
                self.graph.add_dependency(task_id, dep_id)

    def get_execution_plan(self) -> ResolutionResult[str]:
        return self.resolver.resolve()

    def get_next_batch(
        self,
        completed: set[str],
        running: set[str],
        max_batch_size: int = 10
    ) -> list[str]:
        ready = self.resolver.get_ready_tasks(completed, running)
        return ready[:max_batch_size]

    def mark_failed(self, task_id: str) -> set[str]:
        failed = {task_id}
        blocked = self.graph.descendants(task_id)
        return failed | blocked

    def get_task_data(self, task_id: str) -> Any:
        return self._task_data.get(task_id)

    def visualize(self) -> str:
        lines = ["digraph dependencies {"]
        lines.append("  rankdir=LR;")

        levels = self.graph.compute_levels()
        for node_id, level in levels.items():
            lines.append(f'  "{node_id}" [label="{node_id}\\n(level {level})"];')

        for edge in self.graph.edges:
            style = "solid" if edge.dep_type == DependencyType.HARD else "dashed"
            lines.append(f'  "{edge.target}" -> "{edge.source}" [style={style}];')

        lines.append("}")
        return "\n".join(lines)


__all__ = [
    "DependencyType",
    "DependencyStatus",
    "Dependency",
    "DependencyNode",
    "ResolutionResult",
    "DependencyGraph",
    "DependencyResolver",
    "TaskDependencyManager",
]

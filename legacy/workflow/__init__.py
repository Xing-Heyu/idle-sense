"""
Task Chain and Workflow Engine.

This module provides task chaining and workflow orchestration
inspired by Celery chains, groups, and chords.

Usage:
    # Simple chain
    chain = TaskChain()
    chain.add(task1).add(task2).add(task3)
    await chain.execute()

    # Parallel group
    group = TaskGroup([task1, task2, task3])
    await group.execute()

    # Chord (group + callback)
    chord = TaskChord([task1, task2, task3], callback=reduce_task)
    await chord.execute()
"""
import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    """Workflow status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskNodeType(str, Enum):
    """Task node type enumeration."""
    TASK = "task"
    CHAIN = "chain"
    GROUP = "group"
    CHORD = "chord"


@dataclass
class TaskResult:
    """Result of a task execution."""
    task_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class TaskNode:
    """A node in the workflow graph."""
    node_id: str
    node_type: TaskNodeType
    task: Optional[dict[str, Any]] = None
    children: list["TaskNode"] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    result: Optional[TaskResult] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "status": self.status.value,
            "has_result": self.result is not None,
            "children_count": len(self.children),
        }


class WorkflowExecutor(ABC):
    """Abstract base class for workflow executors."""

    @abstractmethod
    async def execute(self, node: TaskNode) -> TaskResult:
        """Execute a task node."""
        pass


class DefaultExecutor(WorkflowExecutor):
    """Default executor that uses the scheduler."""

    def __init__(self, scheduler_url: str = "http://localhost:8000"):
        self.scheduler_url = scheduler_url

    async def execute(self, node: TaskNode) -> TaskResult:
        """Execute a task via the scheduler."""
        if node.task is None:
            return TaskResult(
                task_id=node.node_id,
                success=False,
                error="No task defined"
            )

        start_time = time.time()

        try:
            import requests

            response = requests.post(
                f"{self.scheduler_url}/submit",
                json=node.task,
                timeout=10
            )

            if response.status_code != 200:
                return TaskResult(
                    task_id=node.node_id,
                    success=False,
                    error=f"Submit failed: {response.status_code}"
                )

            task_id = response.json().get("task_id")

            max_wait = node.task.get("timeout", 300)
            waited = 0

            while waited < max_wait:
                response = requests.get(
                    f"{self.scheduler_url}/status/{task_id}",
                    timeout=10
                )

                if response.status_code == 200:
                    status = response.json()

                    if status.get("status") == "completed":
                        return TaskResult(
                            task_id=str(task_id),
                            success=True,
                            result=status.get("result"),
                            execution_time=time.time() - start_time
                        )

                    if status.get("status") == "failed":
                        return TaskResult(
                            task_id=str(task_id),
                            success=False,
                            error=status.get("error"),
                            execution_time=time.time() - start_time
                        )

                await asyncio.sleep(2)
                waited += 2

            return TaskResult(
                task_id=str(task_id),
                success=False,
                error="Timeout waiting for result"
            )

        except Exception as e:
            return TaskResult(
                task_id=node.node_id,
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )


class TaskChain:
    """
    Sequential task chain.

    Tasks are executed one after another, with each task
    receiving the result of the previous task.

    Usage:
        chain = TaskChain()
        chain.add({"code": "result = 1"})
        chain.add({"code": "result = prev_result + 1"})
        results = await chain.execute()
    """

    def __init__(self, executor: Optional[WorkflowExecutor] = None):
        self.executor = executor or DefaultExecutor()
        self.nodes: list[TaskNode] = []
        self.status = WorkflowStatus.PENDING
        self.results: list[TaskResult] = []

    def add(self, task: dict[str, Any]) -> "TaskChain":
        """Add a task to the chain."""
        node = TaskNode(
            node_id=str(uuid.uuid4())[:8],
            node_type=TaskNodeType.TASK,
            task=task
        )

        if self.nodes:
            node.dependencies = [self.nodes[-1].node_id]

        self.nodes.append(node)
        return self

    async def execute(self) -> list[TaskResult]:
        """Execute the chain sequentially."""
        self.status = WorkflowStatus.RUNNING
        self.results = []

        prev_result = None

        for node in self.nodes:
            node.status = WorkflowStatus.RUNNING

            if prev_result is not None:
                node.task["prev_result"] = prev_result

            result = await self.executor.execute(node)
            node.result = result
            node.status = WorkflowStatus.COMPLETED if result.success else WorkflowStatus.FAILED

            self.results.append(result)

            if not result.success:
                self.status = WorkflowStatus.FAILED
                return self.results

            prev_result = result.result

        self.status = WorkflowStatus.COMPLETED
        return self.results

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "chain",
            "status": self.status.value,
            "nodes": [n.to_dict() for n in self.nodes],
            "results_count": len(self.results),
        }


class TaskGroup:
    """
    Parallel task group.

    All tasks are executed in parallel.

    Usage:
        group = TaskGroup([
            {"code": "result = 1"},
            {"code": "result = 2"},
            {"code": "result = 3"},
        ])
        results = await group.execute()
    """

    def __init__(
        self,
        tasks: Optional[list[dict[str, Any]]] = None,
        executor: Optional[WorkflowExecutor] = None
    ):
        self.executor = executor or DefaultExecutor()
        self.nodes: list[TaskNode] = []
        self.status = WorkflowStatus.PENDING
        self.results: list[TaskResult] = []

        if tasks:
            for task in tasks:
                self.add(task)

    def add(self, task: dict[str, Any]) -> "TaskGroup":
        """Add a task to the group."""
        node = TaskNode(
            node_id=str(uuid.uuid4())[:8],
            node_type=TaskNodeType.TASK,
            task=task
        )
        self.nodes.append(node)
        return self

    async def execute(self) -> list[TaskResult]:
        """Execute all tasks in parallel."""
        self.status = WorkflowStatus.RUNNING

        for node in self.nodes:
            node.status = WorkflowStatus.RUNNING

        tasks = [
            self.executor.execute(node)
            for node in self.nodes
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        self.results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.results.append(TaskResult(
                    task_id=self.nodes[i].node_id,
                    success=False,
                    error=str(result)
                ))
            else:
                self.results.append(result)

            self.nodes[i].result = self.results[-1]
            self.nodes[i].status = (
                WorkflowStatus.COMPLETED
                if self.results[-1].success
                else WorkflowStatus.FAILED
            )

        if all(r.success for r in self.results):
            self.status = WorkflowStatus.COMPLETED
        elif any(r.success for r in self.results):
            self.status = WorkflowStatus.FAILED
        else:
            self.status = WorkflowStatus.FAILED

        return self.results

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "group",
            "status": self.status.value,
            "nodes": [n.to_dict() for n in self.nodes],
            "results_count": len(self.results),
        }


class TaskChord:
    """
    Chord: parallel group with callback.

    Executes a group of tasks in parallel, then executes
    a callback with all results.

    Usage:
        chord = TaskChord(
            tasks=[
                {"code": "result = 1"},
                {"code": "result = 2"},
            ],
            callback={"code": "result = sum(results)"}
        )
        result = await chord.execute()
    """

    def __init__(
        self,
        tasks: list[dict[str, Any]],
        callback: dict[str, Any],
        executor: Optional[WorkflowExecutor] = None
    ):
        self.executor = executor or DefaultExecutor()
        self.group = TaskGroup(tasks, executor)
        self.callback_task = callback
        self.status = WorkflowStatus.PENDING
        self.result: Optional[TaskResult] = None

    async def execute(self) -> TaskResult:
        """Execute the chord."""
        self.status = WorkflowStatus.RUNNING

        group_results = await self.group.execute()

        if not all(r.success for r in group_results):
            self.status = WorkflowStatus.FAILED
            return TaskResult(
                task_id="chord",
                success=False,
                error="Group execution failed"
            )

        results = [r.result for r in group_results]

        callback_node = TaskNode(
            node_id=str(uuid.uuid4())[:8],
            node_type=TaskNodeType.TASK,
            task={**self.callback_task, "results": results}
        )

        self.result = await self.executor.execute(callback_node)
        self.status = (
            WorkflowStatus.COMPLETED
            if self.result.success
            else WorkflowStatus.FAILED
        )

        return self.result

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "chord",
            "status": self.status.value,
            "group": self.group.to_dict(),
            "has_result": self.result is not None,
        }


class Workflow:
    """
    Complex workflow with DAG execution.

    Supports:
    - Dependencies between tasks
    - Conditional execution
    - Loops and iterations

    Usage:
        workflow = Workflow()
        workflow.add_task("t1", {"code": "result = 1"})
        workflow.add_task("t2", {"code": "result = 2"}, depends_on=["t1"])
        workflow.add_task("t3", {"code": "result = 3"}, depends_on=["t1"])
        workflow.add_task("t4", {"code": "result = sum(results)"}, depends_on=["t2", "t3"])
        results = await workflow.execute()
    """

    def __init__(self, executor: Optional[WorkflowExecutor] = None):
        self.executor = executor or DefaultExecutor()
        self.nodes: dict[str, TaskNode] = {}
        self.status = WorkflowStatus.PENDING
        self.results: dict[str, TaskResult] = {}

    def add_task(
        self,
        task_id: str,
        task: dict[str, Any],
        depends_on: Optional[list[str]] = None
    ) -> "Workflow":
        """Add a task to the workflow."""
        node = TaskNode(
            node_id=task_id,
            node_type=TaskNodeType.TASK,
            task=task,
            dependencies=depends_on or []
        )

        self.nodes[task_id] = node
        return self

    def _get_ready_tasks(self) -> list[str]:
        """Get tasks ready to execute."""
        ready = []

        for task_id, node in self.nodes.items():
            if node.status != WorkflowStatus.PENDING:
                continue

            all_deps_done = all(
                self.nodes[dep].status == WorkflowStatus.COMPLETED
                for dep in node.dependencies
            )

            any_dep_failed = any(
                self.nodes[dep].status == WorkflowStatus.FAILED
                for dep in node.dependencies
            )

            if any_dep_failed:
                node.status = WorkflowStatus.CANCELLED
                continue

            if all_deps_done:
                ready.append(task_id)

        return ready

    async def execute(self) -> dict[str, TaskResult]:
        """Execute the workflow."""
        self.status = WorkflowStatus.RUNNING

        while True:
            ready = self._get_ready_tasks()

            if not ready:
                break

            tasks = []
            for task_id in ready:
                node = self.nodes[task_id]
                node.status = WorkflowStatus.RUNNING

                dep_results = {
                    dep: self.results[dep].result
                    for dep in node.dependencies
                    if dep in self.results
                }

                if dep_results:
                    node.task["dep_results"] = dep_results

                tasks.append((task_id, self.executor.execute(node)))

            for task_id, coro in tasks:
                result = await coro
                self.results[task_id] = result
                self.nodes[task_id].result = result
                self.nodes[task_id].status = (
                    WorkflowStatus.COMPLETED
                    if result.success
                    else WorkflowStatus.FAILED
                )

        all_completed = all(
            n.status == WorkflowStatus.COMPLETED
            for n in self.nodes.values()
        )

        self.status = WorkflowStatus.COMPLETED if all_completed else WorkflowStatus.FAILED

        return self.results

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "workflow",
            "status": self.status.value,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "results_count": len(self.results),
        }

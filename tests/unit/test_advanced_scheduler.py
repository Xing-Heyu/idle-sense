"""
Unit tests for Advanced Scheduler Module.

Tests:
- ResourceSpec: Resource calculations, fitting
- TaskSpec/NodeSpec: Data structures
- Predicates: Filtering logic
- PriorityFunctions: Scoring logic
- Scheduler: Full scheduling workflow
"""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from legacy.scheduler_v2.advanced_scheduler import (
    AffinitySpec,
    LeastLoadedPriority,
    MostLoadedPriority,
    NodeAffinityPredicate,
    NodeReliabilityPriority,
    NodeSpec,
    NodeState,
    NodeStatePredicate,
    ResourceBalancePriority,
    ResourceFitPredicate,
    ResourceSpec,
    Scheduler,
    SchedulingPolicy,
    SpreadPriority,
    TaintTolerationPredicate,
    TaskAntiAffinityPredicate,
    TaskPriority,
    TaskSpec,
    TaskState,
)


class TestResourceSpec(unittest.TestCase):
    """Test ResourceSpec dataclass."""

    def test_resource_spec_creation(self):
        spec = ResourceSpec(cpu=4.0, memory=8192.0, gpu=2)

        self.assertEqual(spec.cpu, 4.0)
        self.assertEqual(spec.memory, 8192.0)
        self.assertEqual(spec.gpu, 2)

    def test_resource_spec_fits(self):
        available = ResourceSpec(cpu=8.0, memory=16384.0, gpu=2)
        required = ResourceSpec(cpu=4.0, memory=8192.0, gpu=1)

        self.assertTrue(required.fits(available))

        too_much = ResourceSpec(cpu=16.0, memory=8192.0)
        self.assertFalse(too_much.fits(available))

    def test_resource_spec_addition(self):
        r1 = ResourceSpec(cpu=2.0, memory=4096.0)
        r2 = ResourceSpec(cpu=2.0, memory=4096.0)

        result = r1 + r2

        self.assertEqual(result.cpu, 4.0)
        self.assertEqual(result.memory, 8192.0)

    def test_resource_spec_subtraction(self):
        r1 = ResourceSpec(cpu=8.0, memory=16384.0)
        r2 = ResourceSpec(cpu=4.0, memory=8192.0)

        result = r1 - r2

        self.assertEqual(result.cpu, 4.0)
        self.assertEqual(result.memory, 8192.0)

    def test_resource_spec_to_dict(self):
        spec = ResourceSpec(cpu=4.0, memory=8192.0, gpu=1, storage=100.0)

        data = spec.to_dict()

        self.assertEqual(data["cpu"], 4.0)
        self.assertEqual(data["memory"], 8192.0)
        self.assertEqual(data["gpu"], 1)
        self.assertEqual(data["storage"], 100.0)


class TestTaskSpec(unittest.TestCase):
    """Test TaskSpec dataclass."""

    def test_task_spec_creation(self):
        task = TaskSpec(
            task_id="task1",
            name="Test Task",
            priority=TaskPriority.HIGH,
            resources=ResourceSpec(cpu=2.0, memory=4096.0),
        )

        self.assertEqual(task.task_id, "task1")
        self.assertEqual(task.priority, TaskPriority.HIGH)
        self.assertEqual(task.resources.cpu, 2.0)

    def test_task_spec_defaults(self):
        task = TaskSpec(task_id="task1")

        self.assertEqual(task.priority, TaskPriority.NORMAL)
        self.assertEqual(task.state, TaskState.PENDING)
        self.assertEqual(task.max_retries, 3)

    def test_task_spec_serialization(self):
        task = TaskSpec(
            task_id="task1",
            priority=TaskPriority.HIGH,
            resources=ResourceSpec(cpu=2.0),
        )

        data = task.to_dict()

        self.assertEqual(data["task_id"], "task1")
        self.assertEqual(data["priority"], TaskPriority.HIGH.value)


class TestNodeSpec(unittest.TestCase):
    """Test NodeSpec dataclass."""

    def test_node_spec_creation(self):
        node = NodeSpec(
            node_id="node1",
            capacity=ResourceSpec(cpu=8.0, memory=16384.0),
        )

        self.assertEqual(node.node_id, "node1")
        self.assertEqual(node.capacity.cpu, 8.0)

    def test_node_can_fit(self):
        node = NodeSpec(
            node_id="node1",
            capacity=ResourceSpec(cpu=8.0, memory=16384.0),
        )
        node.available = node.capacity

        task_resources = ResourceSpec(cpu=4.0, memory=8192.0)

        self.assertTrue(node.can_fit(task_resources))

    def test_node_allocate(self):
        node = NodeSpec(
            node_id="node1",
            capacity=ResourceSpec(cpu=8.0, memory=16384.0),
            allocated=ResourceSpec(cpu=0.0, memory=0.0),
            available=ResourceSpec(cpu=8.0, memory=16384.0),
        )

        resources = ResourceSpec(cpu=4.0, memory=8192.0)
        result = node.allocate(resources)

        self.assertTrue(result)
        self.assertEqual(node.allocated.cpu, 4.0)
        self.assertEqual(node.available.cpu, 4.0)

    def test_node_allocate_insufficient(self):
        node = NodeSpec(
            node_id="node1",
            capacity=ResourceSpec(cpu=8.0, memory=16384.0),
        )
        node.available = ResourceSpec(cpu=2.0, memory=4096.0)

        resources = ResourceSpec(cpu=4.0, memory=8192.0)
        result = node.allocate(resources)

        self.assertFalse(result)

    def test_node_deallocate(self):
        node = NodeSpec(
            node_id="node1",
            capacity=ResourceSpec(cpu=8.0, memory=16384.0),
            allocated=ResourceSpec(cpu=4.0, memory=8192.0),
            available=ResourceSpec(cpu=4.0, memory=8192.0),
        )

        resources = ResourceSpec(cpu=4.0, memory=8192.0)
        node.deallocate(resources)

        self.assertEqual(node.allocated.cpu, 0.0)
        self.assertEqual(node.available.cpu, 8.0)


class TestPredicates(unittest.TestCase):
    """Test scheduling predicates."""

    def setUp(self):
        self.node = NodeSpec(
            node_id="node1",
            state=NodeState.AVAILABLE,
            capacity=ResourceSpec(cpu=8.0, memory=16384.0),
            labels={"zone": "us-east-1", "gpu": "true"},
        )
        self.node.available = self.node.capacity

        self.task = TaskSpec(
            task_id="task1",
            resources=ResourceSpec(cpu=4.0, memory=8192.0),
        )

    def test_resource_fit_predicate(self):
        predicate = ResourceFitPredicate()

        self.assertTrue(predicate.check(self.node, self.task))

        large_task = TaskSpec(
            task_id="large",
            resources=ResourceSpec(cpu=16.0, memory=32768.0),
        )
        self.assertFalse(predicate.check(self.node, large_task))

    def test_node_state_predicate(self):
        predicate = NodeStatePredicate()

        self.assertTrue(predicate.check(self.node, self.task))

        self.node.state = NodeState.OFFLINE
        self.assertFalse(predicate.check(self.node, self.task))

    def test_node_affinity_predicate(self):
        predicate = NodeAffinityPredicate()

        self.assertTrue(predicate.check(self.node, self.task))

        affinity_task = TaskSpec(
            task_id="affinity_task",
            affinity=AffinitySpec(node_labels={"zone": "us-east-1"}),
        )
        self.assertTrue(predicate.check(self.node, affinity_task))

        wrong_affinity = TaskSpec(
            task_id="wrong_affinity",
            affinity=AffinitySpec(node_labels={"zone": "us-west-1"}),
        )
        self.assertFalse(predicate.check(self.node, wrong_affinity))

    def test_taint_toleration_predicate(self):
        predicate = TaintTolerationPredicate()

        self.assertTrue(predicate.check(self.node, self.task))

        self.node.taints = ["gpu-required"]

        self.assertFalse(predicate.check(self.node, self.task))

        toleration_task = TaskSpec(
            task_id="toleration",
            tolerations=["gpu-required"],
        )
        self.assertTrue(predicate.check(self.node, toleration_task))

    def test_task_anti_affinity_predicate(self):
        predicate = TaskAntiAffinityPredicate()

        self.assertTrue(predicate.check(self.node, self.task))

        self.node.tasks.add("conflicting_task")

        anti_affinity_task = TaskSpec(
            task_id="anti",
            affinity=AffinitySpec(task_anti_affinity=["conflicting_task"]),
        )
        self.assertFalse(predicate.check(self.node, anti_affinity_task))


class TestPriorityFunctions(unittest.TestCase):
    """Test scheduling priority functions."""

    def setUp(self):
        self.node = NodeSpec(
            node_id="node1",
            capacity=ResourceSpec(cpu=8.0, memory=16384.0),
            allocated=ResourceSpec(cpu=4.0, memory=8192.0),
            available=ResourceSpec(cpu=4.0, memory=8192.0),
            reliability_score=0.9,
        )
        self.node.tasks.add("task1")
        self.node.tasks.add("task2")

        self.task = TaskSpec(
            task_id="test_task",
            resources=ResourceSpec(cpu=2.0, memory=4096.0),
        )

    def test_resource_balance_priority(self):
        priority = ResourceBalancePriority()

        score = priority.score(self.node, self.task)

        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)

    def test_least_loaded_priority(self):
        priority = LeastLoadedPriority()

        score = priority.score(self.node, self.task)

        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)

    def test_most_loaded_priority(self):
        priority = MostLoadedPriority()

        score = priority.score(self.node, self.task)

        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)

    def test_node_reliability_priority(self):
        priority = NodeReliabilityPriority()

        score = priority.score(self.node, self.task)

        self.assertEqual(score, 90.0)

    def test_spread_priority(self):
        priority = SpreadPriority()

        score = priority.score(self.node, self.task)

        self.assertEqual(score, 100 / 3)


class TestScheduler(unittest.TestCase):
    """Test Scheduler implementation."""

    def setUp(self):
        self.scheduler = Scheduler(policy=SchedulingPolicy.LEAST_LOADED)

    def test_scheduler_initialization(self):
        self.assertEqual(self.scheduler.policy, SchedulingPolicy.LEAST_LOADED)
        self.assertEqual(len(self.scheduler._nodes), 0)
        self.assertEqual(len(self.scheduler._tasks), 0)

    def test_add_node(self):
        node = NodeSpec(
            node_id="node1",
            capacity=ResourceSpec(cpu=8.0, memory=16384.0),
        )

        self.scheduler.add_node(node)

        self.assertEqual(len(self.scheduler._nodes), 1)
        self.assertEqual(self.scheduler._nodes["node1"].available.cpu, 8.0)

    def test_remove_node(self):
        node = NodeSpec(node_id="node1")
        self.scheduler.add_node(node)

        self.scheduler.remove_node("node1")

        self.assertNotIn("node1", self.scheduler._nodes)

    def test_submit_task(self):
        task = TaskSpec(task_id="task1")

        self.scheduler.submit_task(task)

        self.assertEqual(len(self.scheduler._tasks), 1)
        self.assertEqual(len(self.scheduler._queue), 1)
        self.assertEqual(task.state, TaskState.QUEUED)

    def test_cancel_task(self):
        task = TaskSpec(task_id="task1")
        self.scheduler.submit_task(task)

        result = self.scheduler.cancel_task("task1")

        self.assertTrue(result)
        self.assertEqual(len(self.scheduler._tasks), 0)
        self.assertEqual(len(self.scheduler._queue), 0)

    def test_schedule_basic(self):
        node = NodeSpec(
            node_id="node1",
            capacity=ResourceSpec(cpu=8.0, memory=16384.0),
        )
        self.scheduler.add_node(node)

        task = TaskSpec(
            task_id="task1",
            resources=ResourceSpec(cpu=2.0, memory=4096.0),
        )
        self.scheduler.submit_task(task)

        results = asyncio.run(self.scheduler.schedule())

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "task1")
        self.assertEqual(results[0][1], "node1")
        self.assertEqual(task.state, TaskState.ASSIGNED)

    def test_schedule_insufficient_resources(self):
        node = NodeSpec(
            node_id="node1",
            capacity=ResourceSpec(cpu=2.0, memory=4096.0),
        )
        self.scheduler.add_node(node)

        task = TaskSpec(
            task_id="task1",
            resources=ResourceSpec(cpu=8.0, memory=16384.0),
        )
        self.scheduler.submit_task(task)

        results = asyncio.run(self.scheduler.schedule())

        self.assertEqual(results[0][1], None)
        self.assertEqual(task.state, TaskState.PENDING)

    def test_schedule_priority_order(self):
        node = NodeSpec(
            node_id="node1",
            capacity=ResourceSpec(cpu=8.0, memory=16384.0),
        )
        self.scheduler.add_node(node)

        low_task = TaskSpec(
            task_id="low",
            priority=TaskPriority.LOW,
            resources=ResourceSpec(cpu=2.0, memory=4096.0),
        )
        high_task = TaskSpec(
            task_id="high",
            priority=TaskPriority.HIGH,
            resources=ResourceSpec(cpu=2.0, memory=4096.0),
        )

        self.scheduler.submit_task(low_task)
        self.scheduler.submit_task(high_task)

        results = asyncio.run(self.scheduler.schedule())

        self.assertEqual(results[0][0], "high")
        self.assertEqual(results[1][0], "low")

    def test_complete_task(self):
        node = NodeSpec(
            node_id="node1",
            capacity=ResourceSpec(cpu=8.0, memory=16384.0),
        )
        self.scheduler.add_node(node)

        task = TaskSpec(
            task_id="task1",
            resources=ResourceSpec(cpu=2.0, memory=4096.0),
        )
        self.scheduler.submit_task(task)

        asyncio.run(self.scheduler.schedule())

        self.scheduler.complete_task("task1")

        self.assertEqual(task.state, TaskState.COMPLETED)
        self.assertEqual(node.available.cpu, 8.0)

    def test_get_stats(self):
        node = NodeSpec(node_id="node1")
        self.scheduler.add_node(node)

        task = TaskSpec(task_id="task1")
        self.scheduler.submit_task(task)

        stats = self.scheduler.get_stats()

        self.assertEqual(stats["total_nodes"], 1)
        self.assertEqual(stats["queued_tasks"], 1)

    def test_get_cluster_resources(self):
        scheduler = Scheduler(policy=SchedulingPolicy.LEAST_LOADED)

        node1 = NodeSpec(
            node_id="node1",
            capacity=ResourceSpec(cpu=8.0, memory=16384.0, gpu=0, storage=0.0, network=0.0),
        )
        node2 = NodeSpec(
            node_id="node2",
            capacity=ResourceSpec(cpu=4.0, memory=8192.0, gpu=0, storage=0.0, network=0.0),
        )
        scheduler.add_node(node1)
        scheduler.add_node(node2)

        resources = scheduler.get_cluster_resources()

        self.assertEqual(resources["capacity"]["cpu"], 12.0)
        self.assertEqual(resources["capacity"]["memory"], 24576.0)


class TestSchedulingPolicies(unittest.TestCase):
    """Test different scheduling policies."""

    def test_round_robin_policy(self):
        scheduler = Scheduler(policy=SchedulingPolicy.ROUND_ROBIN)

        for i in range(3):
            node = NodeSpec(
                node_id=f"node{i}",
                capacity=ResourceSpec(cpu=8.0, memory=16384.0),
            )
            scheduler.add_node(node)

        for i in range(3):
            task = TaskSpec(
                task_id=f"task{i}",
                resources=ResourceSpec(cpu=2.0, memory=4096.0),
            )
            scheduler.submit_task(task)

        results = asyncio.run(scheduler.schedule())

        assigned_nodes = [r[1] for r in results]
        self.assertEqual(len(set(assigned_nodes)), 3)

    def test_spread_policy(self):
        scheduler = Scheduler(policy=SchedulingPolicy.SPREAD)

        for i in range(3):
            node = NodeSpec(
                node_id=f"node{i}",
                capacity=ResourceSpec(cpu=8.0, memory=16384.0),
            )
            scheduler.add_node(node)

        for i in range(3):
            task = TaskSpec(
                task_id=f"task{i}",
                resources=ResourceSpec(cpu=2.0, memory=4096.0),
            )
            scheduler.submit_task(task)

        results = asyncio.run(scheduler.schedule())

        assigned_nodes = [r[1] for r in results]
        self.assertEqual(len(set(assigned_nodes)), 3)


class TestPreemption(unittest.TestCase):
    """Test task preemption."""

    def test_preemption_high_priority(self):
        scheduler = Scheduler(policy=SchedulingPolicy.LEAST_LOADED)

        node = NodeSpec(
            node_id="node1",
            capacity=ResourceSpec(cpu=4.0, memory=8192.0),
        )
        scheduler.add_node(node)

        low_task = TaskSpec(
            task_id="low",
            priority=TaskPriority.LOW,
            resources=ResourceSpec(cpu=4.0, memory=8192.0),
        )
        scheduler.submit_task(low_task)
        asyncio.run(scheduler.schedule())

        high_task = TaskSpec(
            task_id="high",
            priority=TaskPriority.HIGH,
            resources=ResourceSpec(cpu=4.0, memory=8192.0),
        )
        scheduler.submit_task(high_task)
        asyncio.run(scheduler.schedule())

        self.assertEqual(low_task.state, TaskState.PREEMPTED)
        self.assertEqual(high_task.state, TaskState.ASSIGNED)


class TestIntegration(unittest.TestCase):
    """Integration tests for scheduler."""

    def test_full_scheduling_workflow(self):
        scheduler = Scheduler(policy=SchedulingPolicy.LEAST_LOADED)

        for i in range(5):
            node = NodeSpec(
                node_id=f"node{i}",
                capacity=ResourceSpec(cpu=8.0, memory=16384.0),
                labels={"zone": f"zone{i % 2}"},
            )
            scheduler.add_node(node)

        for i in range(10):
            task = TaskSpec(
                task_id=f"task{i}",
                priority=TaskPriority.NORMAL if i % 2 == 0 else TaskPriority.LOW,
                resources=ResourceSpec(cpu=2.0, memory=4096.0),
            )
            scheduler.submit_task(task)

        results = asyncio.run(scheduler.schedule())

        scheduled = [r for r in results if r[1] is not None]
        self.assertEqual(len(scheduled), 10)

        stats = scheduler.get_stats()
        self.assertEqual(stats["scheduled"], 10)

    def test_affinity_constraints(self):
        scheduler = Scheduler(policy=SchedulingPolicy.LEAST_LOADED)

        node1 = NodeSpec(
            node_id="node1",
            capacity=ResourceSpec(cpu=8.0, memory=16384.0),
            labels={"gpu": "true"},
        )
        node2 = NodeSpec(
            node_id="node2",
            capacity=ResourceSpec(cpu=8.0, memory=16384.0),
            labels={"gpu": "false"},
        )
        scheduler.add_node(node1)
        scheduler.add_node(node2)

        task = TaskSpec(
            task_id="gpu_task",
            resources=ResourceSpec(cpu=2.0, memory=4096.0),
            affinity=AffinitySpec(node_labels={"gpu": "true"}),
        )
        scheduler.submit_task(task)

        results = asyncio.run(scheduler.schedule())

        self.assertEqual(results[0][1], "node1")


if __name__ == "__main__":
    unittest.main(verbosity=2)

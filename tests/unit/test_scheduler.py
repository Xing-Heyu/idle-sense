"""Unit tests for scheduler module."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from legacy.scheduler.simple_server import (
    NodeHeartbeat,
    NodeRegistration,
    OptimizedMemoryStorage,
    TaskSubmission,
)


def get_sample_task():
    return {
        "code": "print('hello world')",
        "timeout": 300,
        "resources": {"cpu": 1.0, "memory": 512},
    }


def get_sample_node_info():
    return NodeRegistration(
        node_id="node_001",
        capacity={"cpu": 4.0, "memory": 8192},
        tags={"gpu": "false"},
    )


class TestTaskSubmission(unittest.TestCase):
    """Tests for TaskSubmission model."""

    def test_default_values(self):
        task = TaskSubmission(code="print('hello')")
        self.assertEqual(task.timeout, 300)
        self.assertEqual(task.resources, {"cpu": 1.0, "memory": 512})
        self.assertIsNone(task.user_id)

    def test_custom_values(self):
        task = TaskSubmission(
            code="print('hello')",
            timeout=600,
            resources={"cpu": 2.0, "memory": 1024},
            user_id="user_001",
        )
        self.assertEqual(task.timeout, 600)
        self.assertEqual(task.resources["cpu"], 2.0)
        self.assertEqual(task.user_id, "user_001")


class TestNodeHeartbeat(unittest.TestCase):
    """Tests for NodeHeartbeat model."""

    def test_required_fields(self):
        heartbeat = NodeHeartbeat(
            node_id="node_001",
            current_load={"cpu": 50.0, "memory": 60.0},
            is_idle=True,
            available_resources={"cpu": 2.0, "memory": 4096},
        )
        self.assertEqual(heartbeat.node_id, "node_001")
        self.assertTrue(heartbeat.is_idle)

    def test_optional_fields(self):
        heartbeat = NodeHeartbeat(
            node_id="node_001",
            current_load={},
            is_idle=False,
            available_resources={},
            cpu_usage=75.0,
            memory_usage=80.0,
            is_available=False,
        )
        self.assertEqual(heartbeat.cpu_usage, 75.0)
        self.assertEqual(heartbeat.memory_usage, 80.0)
        self.assertFalse(heartbeat.is_available)


class TestOptimizedMemoryStorage(unittest.TestCase):
    """Tests for OptimizedMemoryStorage class."""

    def setUp(self):
        self.storage = OptimizedMemoryStorage()
        self.sample_task = get_sample_task()
        self.sample_node_info = get_sample_node_info()

    def test_initial_state(self):
        self.assertEqual(len(self.storage.tasks), 0)
        self.assertEqual(len(self.storage.nodes), 0)
        self.assertEqual(len(self.storage.pending_tasks), 0)

    def test_add_task(self):
        task_id = self.storage.add_task(
            code=self.sample_task["code"],
            timeout=self.sample_task["timeout"],
            resources=self.sample_task["resources"],
        )
        self.assertIsNotNone(task_id)
        self.assertIn(task_id, self.storage.tasks)
        self.assertEqual(self.storage.tasks[task_id].status, "pending")

    def test_get_task_status(self):
        task_id = self.storage.add_task(
            code=self.sample_task["code"],
            timeout=self.sample_task["timeout"],
            resources=self.sample_task["resources"],
        )
        task_status = self.storage.get_task_status(task_id)
        self.assertIsNotNone(task_status)
        self.assertEqual(task_status["task_id"], task_id)

    def test_get_nonexistent_task(self):
        task = self.storage.get_task_status(99999)
        self.assertIsNone(task)

    def test_register_node(self):
        self.storage.register_node(self.sample_node_info)
        self.assertIn(self.sample_node_info.node_id, self.storage.nodes)

    def test_update_heartbeat(self):
        node_id = self.sample_node_info.node_id
        self.storage.register_node(self.sample_node_info)

        heartbeat = NodeHeartbeat(
            node_id=node_id,
            current_load={"cpu_usage": 30.0, "memory_usage": 50.0},
            is_idle=True,
            available_resources={"cpu": 3.0, "memory": 6000},
        )

        self.storage.update_node_heartbeat(heartbeat)
        self.assertIn(node_id, self.storage.node_heartbeats)

    def test_get_node_status_offline(self):
        self.storage.register_node(
            NodeRegistration(node_id="node_001", capacity={"cpu": 4.0, "memory": 8192})
        )

        status = self.storage._get_node_status("node_001")
        self.assertIn(status["status"], ["offline", "online_available", "online_busy"])

    def test_get_node_status_available(self):
        node_id = "node_001"
        self.storage.register_node(
            NodeRegistration(node_id=node_id, capacity={"cpu": 4.0, "memory": 8192})
        )

        heartbeat = NodeHeartbeat(
            node_id=node_id,
            current_load={"cpu_usage": 0.5, "memory_usage": 30.0},
            is_idle=True,
            available_resources={"cpu": 4.0, "memory": 8192},
        )
        self.storage.update_node_heartbeat(heartbeat)

        status = self.storage._get_node_status(node_id)
        self.assertIn(status["status"], ["online_available", "online_busy", "online_idle"])

    def test_get_task_for_node(self):
        node_id = "node_001"
        self.storage.register_node(
            NodeRegistration(node_id=node_id, capacity={"cpu": 4.0, "memory": 8192})
        )

        heartbeat = NodeHeartbeat(
            node_id=node_id,
            current_load={"cpu_usage": 0.5, "memory_usage": 30.0},
            is_idle=True,
            available_resources={"cpu": 4.0, "memory": 8192},
        )
        self.storage.update_node_heartbeat(heartbeat)

        self.storage.add_task(
            code=self.sample_task["code"],
            timeout=self.sample_task["timeout"],
            resources=self.sample_task["resources"],
        )

        task = self.storage.get_task_for_node(node_id)
        self.assertIsNotNone(task)

    def test_complete_task(self):
        node_id = "node_001"
        self.storage.register_node(
            NodeRegistration(node_id=node_id, capacity={"cpu": 4.0, "memory": 8192})
        )

        heartbeat = NodeHeartbeat(
            node_id=node_id,
            current_load={"cpu_usage": 0.5, "memory_usage": 30.0},
            is_idle=True,
            available_resources={"cpu": 4.0, "memory": 8192},
        )
        self.storage.update_node_heartbeat(heartbeat)

        task_id = self.storage.add_task(
            code=self.sample_task["code"],
            timeout=self.sample_task["timeout"],
            resources=self.sample_task["resources"],
        )

        self.storage.get_task_for_node(node_id)

        result = self.storage.complete_task(task_id, "test result", node_id)
        self.assertTrue(result)

        task_status = self.storage.get_task_status(task_id)
        self.assertEqual(task_status["status"], "completed")
        self.assertEqual(task_status["result"], "test result")

    def test_get_all_results(self):
        node_id = "node_001"
        self.storage.register_node(
            NodeRegistration(node_id=node_id, capacity={"cpu": 4.0, "memory": 8192})
        )

        heartbeat = NodeHeartbeat(
            node_id=node_id,
            current_load={"cpu_usage": 0.5, "memory_usage": 30.0},
            is_idle=True,
            available_resources={"cpu": 4.0, "memory": 8192},
        )
        self.storage.update_node_heartbeat(heartbeat)

        task_id = self.storage.add_task(
            code=self.sample_task["code"],
            timeout=self.sample_task["timeout"],
            resources=self.sample_task["resources"],
        )

        self.storage.get_task_for_node(node_id)
        self.storage.complete_task(task_id, "test result", node_id)

        results = self.storage.get_all_results()
        self.assertEqual(len(results), 1)


class TestTaskMatching(unittest.TestCase):
    """Tests for task-node matching algorithm."""

    def setUp(self):
        self.storage = OptimizedMemoryStorage()

    def test_resource_match(self):
        node_id = "node_001"
        self.storage.register_node(
            NodeRegistration(node_id=node_id, capacity={"cpu": 4.0, "memory": 8192})
        )

        heartbeat = NodeHeartbeat(
            node_id=node_id,
            current_load={"cpu_usage": 0.5, "memory_usage": 20.0},
            is_idle=True,
            available_resources={"cpu": 3.5, "memory": 6000},
        )
        self.storage.update_node_heartbeat(heartbeat)

        self.storage.add_task(code="print('test')", resources={"cpu": 2.0, "memory": 2048})

        matched_task = self.storage.get_task_for_node(node_id)
        self.assertIsNotNone(matched_task)

    def test_resource_mismatch(self):
        node_id = "node_001"
        self.storage.register_node(
            NodeRegistration(node_id=node_id, capacity={"cpu": 1.0, "memory": 512})
        )

        heartbeat = NodeHeartbeat(
            node_id=node_id,
            current_load={"cpu_usage": 10.0, "memory_usage": 20.0},
            is_idle=True,
            available_resources={"cpu": 0.5, "memory": 256},
        )
        self.storage.update_node_heartbeat(heartbeat)

        self.storage.add_task(code="print('test')", resources={"cpu": 2.0, "memory": 2048})

        matched_task = self.storage.get_task_for_node(node_id)
        self.assertIsNone(matched_task)


class TestStatistics(unittest.TestCase):
    """Tests for storage statistics."""

    def setUp(self):
        self.storage = OptimizedMemoryStorage()
        self.sample_task = get_sample_task()

    def test_empty_stats(self):
        stats = self.storage.get_system_stats()
        self.assertEqual(stats["tasks"]["total"], 0)
        self.assertEqual(stats["nodes"]["total"], 0)

    def test_task_stats(self):
        self.storage.add_task(
            code=self.sample_task["code"],
            timeout=self.sample_task["timeout"],
            resources=self.sample_task["resources"],
        )
        self.storage.add_task(
            code=self.sample_task["code"],
            timeout=self.sample_task["timeout"],
            resources=self.sample_task["resources"],
        )

        stats = self.storage.get_system_stats()
        self.assertEqual(stats["tasks"]["total"], 2)
        self.assertEqual(stats["tasks"]["pending"], 2)

    def test_node_stats(self):
        self.storage.register_node(
            NodeRegistration(node_id="node_001", capacity={"cpu": 4.0, "memory": 8192})
        )

        stats = self.storage.get_system_stats()
        self.assertEqual(stats["nodes"]["total"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""
统一调度器模块测试
"""

import time

import pytest

from src.infrastructure.scheduler import (
    AdvancedScheduler,
    NodeInfo,
    ResourceBalancePlugin,
    ResourcePredicate,
    SchedulingPolicy,
    SimpleScheduler,
    TagPredicate,
    TaskInfo,
)


class TestSimpleScheduler:
    """简单调度器测试"""

    def test_scheduler_initialization(self):
        """测试调度器初始化"""
        scheduler = SimpleScheduler()

        assert scheduler.tasks == {}
        assert scheduler.pending_tasks == []
        assert scheduler.nodes == {}
        assert len(scheduler.predicates) > 0
        assert len(scheduler.priority_plugins) > 0

    def test_register_node(self):
        """测试节点注册"""
        scheduler = SimpleScheduler()

        node = NodeInfo(
            node_id="test-node-1", capacity={"cpu": 4.0, "memory": 8192}, tags={"type": "worker"}
        )

        result = scheduler.register_node(node)

        assert result is True
        assert "test-node-1" in scheduler.nodes
        assert scheduler.stats["nodes_registered"] == 1

    def test_add_task(self):
        """测试添加任务"""
        scheduler = SimpleScheduler()

        task = TaskInfo(
            task_id=0, code="print('hello')", required_resources={"cpu": 1.0, "memory": 512}
        )

        task_id = scheduler.add_task(task)

        assert task_id == "1"
        assert "1" in scheduler.tasks
        assert "1" in scheduler.pending_tasks

    def test_get_task_for_node(self):
        """测试节点获取任务"""
        scheduler = SimpleScheduler()

        node = NodeInfo(
            node_id="test-node-1",
            capacity={"cpu": 4.0, "memory": 8192},
            available_resources={"cpu": 4.0, "memory": 8192},
            is_idle=True,
            is_available=True,
        )
        scheduler.register_node(node)
        scheduler.node_heartbeats["test-node-1"] = time.time()

        task = TaskInfo(
            task_id=0, code="print('hello')", required_resources={"cpu": 1.0, "memory": 512}
        )
        scheduler.add_task(task)

        task = scheduler.tasks["1"]
        assert task.status in ["assigned", "pending"]

        if task.status == "assigned":
            assert task.assigned_node == "test-node-1"
        else:
            assigned_task = scheduler.get_task_for_node("test-node-1")
            assert assigned_task is not None
            assert assigned_task.status == "assigned"

    def test_complete_task(self):
        """测试完成任务"""
        scheduler = SimpleScheduler()

        node = NodeInfo(
            node_id="test-node-1",
            capacity={"cpu": 4.0, "memory": 8192},
            available_resources={"cpu": 4.0, "memory": 8192},
            is_idle=True,
            is_available=True,
        )
        scheduler.register_node(node)
        scheduler.node_heartbeats["test-node-1"] = time.time()

        task = TaskInfo(
            task_id=0, code="print('hello')", required_resources={"cpu": 1.0, "memory": 512}
        )
        scheduler.add_task(task)
        scheduler.get_task_for_node("test-node-1")

        result = scheduler.complete_task("1", "hello")

        assert result is True
        assert scheduler.tasks["1"].status == "completed"
        assert scheduler.tasks["1"].result == "hello"

    def test_get_system_stats(self):
        """测试获取系统统计"""
        scheduler = SimpleScheduler()

        stats = scheduler.get_system_stats()

        assert "tasks" in stats
        assert "nodes" in stats
        assert "scheduler" in stats
        assert stats["tasks"]["total"] == 0
        assert stats["nodes"]["total"] == 0


class TestAdvancedScheduler:
    """高级调度器测试"""

    def test_fifo_scheduling(self):
        """测试FIFO调度"""
        scheduler = AdvancedScheduler(policy=SchedulingPolicy.FIFO)

        node = NodeInfo(
            node_id="test-node-1",
            capacity={"cpu": 4.0, "memory": 8192},
            available_resources={"cpu": 4.0, "memory": 8192},
            is_idle=True,
            is_available=True,
        )
        scheduler.register_node(node)
        scheduler.node_heartbeats["test-node-1"] = time.time()

        task1 = TaskInfo(task_id=0, code="print('1')", user_id="user1")
        TaskInfo(task_id=0, code="print('2')", user_id="user2")

        scheduler.add_task(task1)

        task = scheduler.tasks["1"]
        assert task.status in ["assigned", "pending"]
        if task.status == "assigned":
            assert task.assigned_node == "test-node-1"

    def test_priority_scheduling(self):
        """测试优先级调度"""
        scheduler = AdvancedScheduler(policy=SchedulingPolicy.PRIORITY)

        node = NodeInfo(
            node_id="test-node-1",
            capacity={"cpu": 4.0, "memory": 8192},
            available_resources={"cpu": 4.0, "memory": 8192},
            is_idle=True,
            is_available=True,
        )
        scheduler.register_node(node)
        scheduler.node_heartbeats["test-node-1"] = time.time()

        task1 = TaskInfo(task_id=0, code="print('low')", priority=1)
        TaskInfo(task_id=0, code="print('high')", priority=10)

        scheduler.add_task(task1)

        task = scheduler.tasks["1"]
        assert task.status in ["assigned", "pending"]
        if task.status == "assigned":
            assert task.assigned_node == "test-node-1"


class TestPredicates:
    """谓词测试"""

    def test_resource_predicate(self):
        """测试资源谓词"""
        predicate = ResourcePredicate()

        task = TaskInfo(
            task_id=1, code="print('hello')", required_resources={"cpu": 2.0, "memory": 1024}
        )

        node_enough = NodeInfo(node_id="node-1", available_resources={"cpu": 4.0, "memory": 2048})

        node_not_enough = NodeInfo(
            node_id="node-2", available_resources={"cpu": 1.0, "memory": 512}
        )

        assert predicate.evaluate(task, node_enough) is True
        assert predicate.evaluate(task, node_not_enough) is False

    def test_tag_predicate(self):
        """测试标签谓词"""
        predicate = TagPredicate(required_tags={"gpu": "true"})

        task = TaskInfo(task_id=1, code="print('hello')")

        node_match = NodeInfo(node_id="node-1", tags={"gpu": "true", "type": "worker"})

        node_no_match = NodeInfo(node_id="node-2", tags={"type": "worker"})

        assert predicate.evaluate(task, node_match) is True
        assert predicate.evaluate(task, node_no_match) is False


class TestPriorityPlugins:
    """优先级插件测试"""

    def test_resource_balance_plugin(self):
        """测试资源均衡插件"""
        plugin = ResourceBalancePlugin()

        task = TaskInfo(
            task_id=1, code="print('hello')", required_resources={"cpu": 1.0, "memory": 512}
        )

        node_idle = NodeInfo(
            node_id="node-1",
            capacity={"cpu": 4.0, "memory": 8192},
            available_resources={"cpu": 4.0, "memory": 8192},
            current_load={"cpu_usage": 0.0, "memory_usage": 0},
            is_idle=True,
        )

        node_busy = NodeInfo(
            node_id="node-2",
            capacity={"cpu": 4.0, "memory": 8192},
            available_resources={"cpu": 1.0, "memory": 2048},
            current_load={"cpu_usage": 3.0, "memory_usage": 6144},
            is_idle=False,
        )

        score_idle = plugin.calculate_score(task, node_idle)
        score_busy = plugin.calculate_score(task, node_busy)

        assert score_idle > score_busy


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

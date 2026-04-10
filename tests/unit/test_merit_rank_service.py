"""
MeritRank 声誉计算引擎单元测试

测试覆盖:
- transmission_decay: 传递衰减函数
- connection_decay: 连接衰减函数
- period_decay: 周期衰减函数
- calculate_reputation: 声誉计算
- 女巫攻击防御效果
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.core.services.merit_rank_service import (
    Feedback,
    MeritRankEngine,
    ReputationEvent,
)


class TestTransmissionDecay(unittest.TestCase):
    """测试传递衰减函数"""

    def setUp(self):
        self.engine = MeritRankEngine()

    def test_transmission_decay_distance_zero(self):
        score = 100.0
        decayed = self.engine._transmission_decay(score, 0)
        self.assertAlmostEqual(decayed, 100.0, places=4)

    def test_transmission_decay_distance_one(self):
        score = 100.0
        decayed = self.engine._transmission_decay(score, 1)
        expected = 100.0 * 0.8
        self.assertAlmostEqual(decayed, expected, places=4)

    def test_transmission_decay_distance_two(self):
        score = 100.0
        decayed = self.engine._transmission_decay(score, 2)
        expected = 100.0 * (0.8**2)
        self.assertAlmostEqual(decayed, expected, places=4)

    def test_transmission_decay_distance_five(self):
        score = 100.0
        decayed = self.engine._transmission_decay(score, 5)
        expected = 100.0 * (0.8**5)
        self.assertAlmostEqual(decayed, expected, places=4)

    def test_transmission_decay_reduces_score(self):
        score = 100.0
        for distance in range(1, 10):
            decayed = self.engine._transmission_decay(score, distance)
            self.assertLess(decayed, score)

    def test_transmission_decay_negative_score(self):
        score = -50.0
        decayed = self.engine._transmission_decay(score, 2)
        expected = -50.0 * (0.8**2)
        self.assertAlmostEqual(decayed, expected, places=4)


class TestConnectionDecay(unittest.TestCase):
    """测试连接衰减函数"""

    def setUp(self):
        self.engine = MeritRankEngine()

    def test_connection_decay_single_connection(self):
        score = 100.0
        decayed = self.engine._connection_decay(score, 1)
        expected = 100.0 * (1.0 / (1**1.5))
        self.assertAlmostEqual(decayed, expected, places=4)

    def test_connection_decay_multiple_connections(self):
        score = 100.0
        decayed = self.engine._connection_decay(score, 10)
        expected = 100.0 * (1.0 / (10**1.5))
        self.assertAlmostEqual(decayed, expected, places=4)

    def test_connection_decay_zero_connections(self):
        score = 100.0
        decayed = self.engine._connection_decay(score, 0)
        self.assertEqual(decayed, 100.0)

    def test_connection_decay_super_exponential(self):
        score = 100.0
        decayed_10 = self.engine._connection_decay(score, 10)
        decayed_100 = self.engine._connection_decay(score, 100)
        ratio = decayed_100 / decayed_10
        self.assertLess(ratio, 0.1)

    def test_connection_decay_high_connections(self):
        score = 100.0
        decayed = self.engine._connection_decay(score, 1000)
        self.assertLess(decayed, 1.0)


class TestPeriodDecay(unittest.TestCase):
    """测试周期衰减函数"""

    def setUp(self):
        self.engine = MeritRankEngine()

    def test_period_decay_zero_periods(self):
        score = 100.0
        decayed = self.engine._period_decay(score, 0)
        self.assertAlmostEqual(decayed, 100.0, places=4)

    def test_period_decay_one_period(self):
        score = 100.0
        decayed = self.engine._period_decay(score, 1)
        expected = 100.0 * 0.95
        self.assertAlmostEqual(decayed, expected, places=4)

    def test_period_decay_multiple_periods(self):
        score = 100.0
        decayed = self.engine._period_decay(score, 10)
        expected = 100.0 * (0.95**10)
        self.assertAlmostEqual(decayed, expected, places=4)

    def test_period_decay_reduces_score(self):
        score = 100.0
        for periods in range(1, 20):
            decayed = self.engine._period_decay(score, periods)
            self.assertLess(decayed, score)

    def test_period_decay_long_term(self):
        score = 100.0
        decayed = self.engine._period_decay(score, 52)
        self.assertLess(decayed, 10.0)


class TestCalculateReputation(unittest.TestCase):
    """测试声誉计算"""

    def setUp(self):
        self.engine = MeritRankEngine()

    def test_default_reputation(self):
        reputation = self.engine.get_reputation("new_address")
        self.assertEqual(reputation, MeritRankEngine.DEFAULT_REPUTATION)

    def test_single_feedback(self):
        feedback = Feedback(from_address="user1", to_address="user2", score=10.0, distance=1)
        self.engine.add_feedback(feedback)

        reputation = self.engine.get_reputation("user2")
        self.assertGreater(reputation, MeritRankEngine.DEFAULT_REPUTATION)

    def test_multiple_feedbacks(self):
        for i in range(5):
            feedback = Feedback(
                from_address=f"user{i}", to_address="target", score=10.0, distance=1
            )
            self.engine.add_feedback(feedback)

        reputation = self.engine.get_reputation("target")
        self.assertGreater(reputation, MeritRankEngine.DEFAULT_REPUTATION)

    def test_reputation_bounds_max(self):
        for i in range(100):
            feedback = Feedback(
                from_address=f"user{i}", to_address="target", score=100.0, distance=1
            )
            self.engine.add_feedback(feedback)

        reputation = self.engine.get_reputation("target")
        self.assertLessEqual(reputation, MeritRankEngine.MAX_REPUTATION)

    def test_reputation_bounds_min(self):
        for i in range(100):
            feedback = Feedback(
                from_address=f"user{i}", to_address="target", score=-100.0, distance=1
            )
            self.engine.add_feedback(feedback)

        reputation = self.engine.get_reputation("target")
        self.assertGreaterEqual(reputation, MeritRankEngine.MIN_REPUTATION)

    def test_negative_feedback_reduces_reputation(self):
        initial = self.engine.get_reputation("target")

        feedback = Feedback(from_address="user1", to_address="target", score=-50.0, distance=1)
        self.engine.add_feedback(feedback)

        reputation = self.engine.get_reputation("target")
        self.assertLess(reputation, initial)

    def test_distance_affects_reputation(self):
        feedback_near = Feedback(from_address="user1", to_address="target1", score=10.0, distance=1)
        feedback_far = Feedback(from_address="user2", to_address="target2", score=10.0, distance=5)

        self.engine.add_feedback(feedback_near)
        self.engine.add_feedback(feedback_far)

        rep_near = self.engine.get_reputation("target1")
        rep_far = self.engine.get_reputation("target2")

        self.assertGreater(rep_near, rep_far)

    def test_task_completion_increases_reputation(self):
        initial = self.engine.get_reputation("worker1")

        self.engine.record_task_completion(
            node_address="worker1", requester_address="requester1", quality_score=1.0
        )

        reputation = self.engine.get_reputation("worker1")
        self.assertGreater(reputation, initial)

    def test_task_failure_decreases_reputation(self):
        initial = self.engine.get_reputation("worker1")

        self.engine.record_task_failure(node_address="worker1", requester_address="requester1")

        reputation = self.engine.get_reputation("worker1")
        self.assertLess(reputation, initial)

    def test_uptime_reward(self):
        initial = self.engine.get_reputation("node1")

        self.engine.record_uptime_reward(node_address="node1", uptime_minutes=120)

        reputation = self.engine.get_reputation("node1")
        self.assertGreater(reputation, initial)

    def test_uptime_reward_minimum_threshold(self):
        initial = self.engine.get_reputation("node1")

        self.engine.record_uptime_reward(node_address="node1", uptime_minutes=30)

        reputation = self.engine.get_reputation("node1")
        self.assertEqual(reputation, initial)


class TestSybilAttackDefense(unittest.TestCase):
    """测试女巫攻击防御效果"""

    def setUp(self):
        self.engine = MeritRankEngine()

    def test_sybil_attack_simulation(self):
        result = self.engine.simulate_sybil_attack(attacker_count=100, fake_score=5.0)

        self.assertEqual(result["attacker_count"], 100)
        self.assertEqual(result["fake_score_per_attacker"], 5.0)
        self.assertLess(result["effective_score"], result["total_fake_score"])
        self.assertLess(result["decay_ratio"], 0.5)

    def test_sybil_attack_effectiveness(self):
        result = self.engine.simulate_sybil_attack(attacker_count=1000, fake_score=10.0)

        self.assertLess(result["effectiveness"], 0.1)

    def test_connection_decay_prevents_inflation(self):
        engine = MeritRankEngine()

        for i in range(100):
            feedback = Feedback(
                from_address=f"attacker_{i}", to_address="victim", score=10.0, distance=1
            )
            engine.add_feedback(feedback)

        reputation = engine.get_reputation("victim")
        self.assertLess(reputation, MeritRankEngine.MAX_REPUTATION)

    def test_many_connections_reduce_single_weight(self):
        engine = MeritRankEngine()

        engine.add_feedback(Feedback("user1", "target", 10.0, 1))
        rep_single = engine.get_reputation("target")

        engine2 = MeritRankEngine()
        for i in range(50):
            engine2.add_feedback(Feedback(f"user{i}", "target", 10.0, 1))
        rep_many = engine2.get_reputation("target")

        avg_increase_single = (rep_single - 50) / 1
        avg_increase_many = (rep_many - 50) / 50

        self.assertGreater(avg_increase_single, avg_increase_many)


class TestReputationTiers(unittest.TestCase):
    """测试声誉等级"""

    def setUp(self):
        self.engine = MeritRankEngine()

    def test_platinum_tier(self):
        tier = self.engine.get_reputation_tier(95)
        self.assertEqual(tier, "Platinum")

    def test_gold_tier(self):
        tier = self.engine.get_reputation_tier(80)
        self.assertEqual(tier, "Gold")

    def test_silver_tier(self):
        tier = self.engine.get_reputation_tier(65)
        self.assertEqual(tier, "Silver")

    def test_bronze_tier(self):
        tier = self.engine.get_reputation_tier(45)
        self.assertEqual(tier, "Bronze")

    def test_untrusted_tier(self):
        tier = self.engine.get_reputation_tier(30)
        self.assertEqual(tier, "Untrusted")

    def test_scheduling_priority_platinum(self):
        self.engine._reputations["user1"] = 95
        priority = self.engine.get_scheduling_priority("user1")
        self.assertEqual(priority, 3)

    def test_scheduling_priority_untrusted(self):
        self.engine._reputations["user1"] = 30
        priority = self.engine.get_scheduling_priority("user1")
        self.assertEqual(priority, -1)

    def test_is_trusted(self):
        self.engine._reputations["trusted_user"] = 60
        self.engine._reputations["untrusted_user"] = 30

        self.assertTrue(self.engine.is_trusted("trusted_user"))
        self.assertFalse(self.engine.is_trusted("untrusted_user"))


class TestReputationEvents(unittest.TestCase):
    """测试声誉事件记录"""

    def setUp(self):
        self.engine = MeritRankEngine()

    def test_event_recorded_on_feedback(self):
        feedback = Feedback(from_address="user1", to_address="user2", score=10.0, distance=1)
        self.engine.add_feedback(feedback)

        events = self.engine.get_reputation_events("user2")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "reputation_update")

    def test_event_metadata(self):
        feedback = Feedback(from_address="user1", to_address="user2", score=10.0, distance=1)
        self.engine.add_feedback(feedback)

        events = self.engine.get_reputation_events("user2")
        self.assertIn("old_reputation", events[0].metadata)
        self.assertIn("new_reputation", events[0].metadata)

    def test_get_events_by_address(self):
        self.engine.add_feedback(Feedback("user1", "target1", 10.0, 1))
        self.engine.add_feedback(Feedback("user2", "target2", 10.0, 1))

        events = self.engine.get_reputation_events("target1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].address, "target1")


class TestMeritRankStats(unittest.TestCase):
    """测试统计功能"""

    def setUp(self):
        self.engine = MeritRankEngine()

    def test_empty_stats(self):
        stats = self.engine.get_stats()
        self.assertEqual(stats["total_accounts"], 0)
        self.assertEqual(stats["avg_reputation"], 0.0)

    def test_stats_with_accounts(self):
        self.engine._reputations["user1"] = 80
        self.engine._reputations["user2"] = 60

        stats = self.engine.get_stats()
        self.assertEqual(stats["total_accounts"], 2)
        self.assertEqual(stats["avg_reputation"], 70.0)

    def test_tier_distribution(self):
        self.engine._reputations["platinum_user"] = 95
        self.engine._reputations["gold_user"] = 80
        self.engine._reputations["silver_user"] = 65

        stats = self.engine.get_stats()
        self.assertEqual(stats["tier_distribution"]["Platinum"], 1)
        self.assertEqual(stats["tier_distribution"]["Gold"], 1)
        self.assertEqual(stats["tier_distribution"]["Silver"], 1)


class TestFeedbackDataclass(unittest.TestCase):
    """测试 Feedback 数据类"""

    def test_feedback_creation(self):
        feedback = Feedback(from_address="user1", to_address="user2", score=10.0, distance=2)

        self.assertEqual(feedback.from_address, "user1")
        self.assertEqual(feedback.to_address, "user2")
        self.assertEqual(feedback.score, 10.0)
        self.assertEqual(feedback.distance, 2)

    def test_feedback_default_timestamp(self):
        before = time.time()
        feedback = Feedback(from_address="user1", to_address="user2", score=10.0)
        after = time.time()

        self.assertGreaterEqual(feedback.timestamp, before)
        self.assertLessEqual(feedback.timestamp, after)

    def test_feedback_default_distance(self):
        feedback = Feedback(from_address="user1", to_address="user2", score=10.0)

        self.assertEqual(feedback.distance, 1)


class TestReputationEventDataclass(unittest.TestCase):
    """测试 ReputationEvent 数据类"""

    def test_event_creation(self):
        event = ReputationEvent(
            address="user1", event_type="test_event", score_change=10.0, reason="test reason"
        )

        self.assertEqual(event.address, "user1")
        self.assertEqual(event.event_type, "test_event")
        self.assertEqual(event.score_change, 10.0)
        self.assertEqual(event.reason, "test reason")

    def test_event_default_metadata(self):
        event = ReputationEvent(address="user1", event_type="test", score_change=5.0, reason="test")

        self.assertEqual(event.metadata, {})

    def test_event_custom_metadata(self):
        event = ReputationEvent(
            address="user1",
            event_type="test",
            score_change=5.0,
            reason="test",
            metadata={"key": "value"},
        )

        self.assertEqual(event.metadata["key"], "value")


if __name__ == "__main__":
    unittest.main(verbosity=2)

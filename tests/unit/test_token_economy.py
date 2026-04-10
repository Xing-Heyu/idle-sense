"""
Unit tests for Token Economy Module.

Tests:
- PricingEngine: Resource pricing, congestion, estimation
- ReputationSystem: Reputation updates, trust scoring, tiers
- StakingManager: Staking, unstaking, slashing
- TokenEconomy: Full economy operations, payments, rewards
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from legacy.token_economy import (
    Account,
    PricingEngine,
    ReputationAction,
    ReputationSystem,
    ResourceMetrics,
    StakingManager,
    TokenEconomy,
    Transaction,
    TransactionType,
)


class TestResourceMetrics(unittest.TestCase):
    """Test ResourceMetrics dataclass."""

    def test_resource_metrics_creation(self):
        metrics = ResourceMetrics(
            cpu_seconds=100.0,
            memory_gb_seconds=50.0,
            storage_gb=10.0,
            network_gb=5.0,
            gpu_seconds=20.0,
        )
        self.assertEqual(metrics.cpu_seconds, 100.0)
        self.assertEqual(metrics.memory_gb_seconds, 50.0)
        self.assertEqual(metrics.storage_gb, 10.0)

    def test_resource_metrics_serialization(self):
        metrics = ResourceMetrics(
            cpu_seconds=100.0,
            memory_gb_seconds=50.0,
        )

        data = metrics.to_dict()
        restored = ResourceMetrics.from_dict(data)

        self.assertEqual(restored.cpu_seconds, 100.0)
        self.assertEqual(restored.memory_gb_seconds, 50.0)


class TestTransaction(unittest.TestCase):
    """Test Transaction dataclass."""

    def test_transaction_creation(self):
        tx = Transaction(
            tx_id="tx123",
            tx_type=TransactionType.TRANSFER,
            from_address="addr1",
            to_address="addr2",
            amount=100.0,
        )
        self.assertEqual(tx.tx_id, "tx123")
        self.assertEqual(tx.tx_type, TransactionType.TRANSFER)
        self.assertEqual(tx.amount, 100.0)

    def test_transaction_serialization(self):
        tx = Transaction(
            tx_id="tx123",
            tx_type=TransactionType.REWARD,
            from_address="escrow",
            to_address="worker",
            amount=50.0,
            metadata={"task_id": "task1"},
        )

        data = tx.to_dict()
        restored = Transaction.from_dict(data)

        self.assertEqual(restored.tx_id, "tx123")
        self.assertEqual(restored.tx_type, TransactionType.REWARD)
        self.assertEqual(restored.metadata["task_id"], "task1")


class TestAccount(unittest.TestCase):
    """Test Account dataclass."""

    def test_account_creation(self):
        account = Account(
            address="addr123",
            balance=1000.0,
            staked=100.0,
            reputation=75.0,
        )
        self.assertEqual(account.address, "addr123")
        self.assertEqual(account.balance, 1000.0)
        self.assertEqual(account.staked, 100.0)
        self.assertEqual(account.reputation, 75.0)

    def test_account_serialization(self):
        account = Account(
            address="addr123",
            balance=1000.0,
            tasks_completed=10,
            tasks_failed=2,
        )

        data = account.to_dict()
        restored = Account.from_dict(data)

        self.assertEqual(restored.address, "addr123")
        self.assertEqual(restored.balance, 1000.0)
        self.assertEqual(restored.tasks_completed, 10)
        self.assertEqual(restored.tasks_failed, 2)


class TestPricingEngine(unittest.TestCase):
    """Test PricingEngine implementation."""

    def setUp(self):
        self.pricing = PricingEngine()

    def test_pricing_initialization(self):
        self.assertEqual(self.pricing._congestion_level, 1.0)
        self.assertEqual(len(self.pricing._demand_history), 0)

    def test_calculate_price_basic(self):
        resources = ResourceMetrics(
            cpu_seconds=100.0,
            memory_gb_seconds=50.0,
        )

        price = self.pricing.calculate_price(resources)

        expected = 100.0 * PricingEngine.BASE_CPU_PRICE + 50.0 * PricingEngine.BASE_MEMORY_PRICE
        expected_with_fees = expected * (1 + PricingEngine.PRIORITY_FEE_MULTIPLIER)

        self.assertGreater(price, 0)
        self.assertAlmostEqual(price, expected_with_fees, places=4)

    def test_calculate_price_with_priority(self):
        resources = ResourceMetrics(cpu_seconds=100.0)

        price_low = self.pricing.calculate_price(resources, priority=0)
        price_high = self.pricing.calculate_price(resources, priority=5)

        self.assertGreater(price_high, price_low)

    def test_calculate_price_with_urgency(self):
        resources = ResourceMetrics(cpu_seconds=100.0)

        price_normal = self.pricing.calculate_price(resources, urgency_multiplier=1.0)
        price_urgent = self.pricing.calculate_price(resources, urgency_multiplier=2.0)

        self.assertAlmostEqual(price_urgent, price_normal * 2.0, places=4)

    def test_update_congestion(self):
        self.pricing.update_congestion(demand=100.0, supply=50.0)

        self.assertEqual(self.pricing._congestion_level, 2.0)
        self.assertEqual(len(self.pricing._demand_history), 1)

    def test_congestion_bounds(self):
        self.pricing.update_congestion(demand=1000.0, supply=10.0)
        self.assertEqual(self.pricing._congestion_level, 5.0)

        self.pricing.update_congestion(demand=10.0, supply=1000.0)
        self.assertEqual(self.pricing._congestion_level, 0.5)

    def test_estimate_resources(self):
        resources = self.pricing.estimate_resources(
            task_complexity="high",
            estimated_duration=60.0,
            memory_requirement=2.0,
            gpu_required=True,
        )

        self.assertEqual(resources.cpu_seconds, 120.0)
        self.assertEqual(resources.memory_gb_seconds, 120.0)
        self.assertEqual(resources.gpu_seconds, 120.0)

    def test_get_market_stats(self):
        stats = self.pricing.get_market_stats()

        self.assertIn("congestion_level", stats)
        self.assertIn("base_prices", stats)
        self.assertIn("demand_avg", stats)


class TestReputationSystem(unittest.TestCase):
    """Test ReputationSystem implementation."""

    def setUp(self):
        self.reputation = ReputationSystem()
        self.account = Account(address="test_addr", reputation=50.0)

    def test_reputation_initialization(self):
        self.assertEqual(len(self.reputation._reputation_history), 0)

    def test_update_reputation_positive(self):
        new_rep = self.reputation.update_reputation(self.account, ReputationAction.TASK_COMPLETED)

        self.assertGreater(new_rep, 50.0)
        self.assertEqual(self.account.tasks_completed, 1)

    def test_update_reputation_negative(self):
        new_rep = self.reputation.update_reputation(self.account, ReputationAction.TASK_FAILED)

        self.assertLess(new_rep, 50.0)
        self.assertEqual(self.account.tasks_failed, 1)

    def test_malicious_behavior_penalty(self):
        new_rep = self.reputation.update_reputation(
            self.account, ReputationAction.MALICIOUS_BEHAVIOR
        )

        self.assertLess(new_rep, 50.0)
        self.assertLess(new_rep, 40.0)

    def test_reputation_bounds(self):
        for _ in range(100):
            self.reputation.update_reputation(self.account, ReputationAction.TASK_COMPLETED)

        self.assertLessEqual(self.account.reputation, ReputationSystem.MAX_REPUTATION)

        self.account.reputation = 50.0
        for _ in range(100):
            self.reputation.update_reputation(self.account, ReputationAction.MALICIOUS_BEHAVIOR)

        self.assertGreaterEqual(self.account.reputation, ReputationSystem.MIN_REPUTATION)

    def test_decay_reputation(self):
        self.account.reputation = 80.0

        decayed = self.reputation.decay_reputation(self.account)

        self.assertLess(decayed, 80.0)
        self.assertGreater(decayed, 50.0)

    def test_get_trust_score(self):
        self.account.reputation = 80.0
        self.account.tasks_completed = 9
        self.account.tasks_failed = 1

        trust = self.reputation.get_trust_score(self.account)

        self.assertGreater(trust, 0.5)
        self.assertLessEqual(trust, 1.0)

    def test_get_reputation_tier(self):
        self.assertEqual(self.reputation.get_reputation_tier(95), "Platinum")
        self.assertEqual(self.reputation.get_reputation_tier(80), "Gold")
        self.assertEqual(self.reputation.get_reputation_tier(65), "Silver")
        self.assertEqual(self.reputation.get_reputation_tier(45), "Bronze")
        self.assertEqual(self.reputation.get_reputation_tier(20), "Untrusted")

    def test_get_history(self):
        self.reputation.update_reputation(self.account, ReputationAction.TASK_COMPLETED)
        self.reputation.update_reputation(self.account, ReputationAction.UPTIME_GOOD)

        history = self.reputation.get_history("test_addr")

        self.assertEqual(len(history), 2)


class TestStakingManager(unittest.TestCase):
    """Test StakingManager implementation."""

    def setUp(self):
        self.staking = StakingManager()
        self.account = Account(address="staker", balance=1000.0)

    def test_stake_success(self):
        result = self.staking.stake(self.account, 100.0)

        self.assertTrue(result)
        self.assertEqual(self.account.balance, 900.0)
        self.assertEqual(self.account.staked, 100.0)

    def test_stake_minimum(self):
        result = self.staking.stake(self.account, 5.0)

        self.assertFalse(result)
        self.assertEqual(self.account.balance, 1000.0)

    def test_stake_insufficient_balance(self):
        result = self.staking.stake(self.account, 2000.0)

        self.assertFalse(result)

    def test_unstake_after_lock_period(self):
        self.staking.stake(self.account, 100.0)

        for _stake_id, stake in self.staking._stakes.items():
            stake["unlock_at"] = time.time() - 1

        unstaked = self.staking.unstake(self.account, 100.0)

        self.assertEqual(unstaked, 100.0)
        self.assertEqual(self.account.balance, 1000.0)
        self.assertEqual(self.account.staked, 0.0)

    def test_unstake_before_lock_period(self):
        self.staking.stake(self.account, 100.0)

        unstaked = self.staking.unstake(self.account, 100.0)

        self.assertEqual(unstaked, 0.0)
        self.assertEqual(self.account.staked, 100.0)

    def test_slash(self):
        self.staking.stake(self.account, 100.0)

        slash_amount = self.staking.slash(self.account, "test violation")

        self.assertGreater(slash_amount, 0)
        self.assertLess(self.account.staked, 100.0)

    def test_get_stake_info(self):
        self.staking.stake(self.account, 100.0)

        info = self.staking.get_stake_info("staker")

        self.assertEqual(info["total_staked"], 100.0)
        self.assertEqual(len(info["active_stakes"]), 1)


class TestTokenEconomy(unittest.TestCase):
    """Test TokenEconomy implementation."""

    def setUp(self):
        self.economy = TokenEconomy()

    def test_economy_initialization(self):
        self.assertEqual(self.economy.TOKEN_SYMBOL, "CMP")
        self.assertIsNotNone(self.economy.pricing)
        self.assertIsNotNone(self.economy.reputation)
        self.assertIsNotNone(self.economy.staking)

    def test_create_account(self):
        account = self.economy.create_account("user1", initial_balance=100.0)

        self.assertEqual(account.address, "user1")
        self.assertEqual(account.balance, 100.0)

    def test_get_account(self):
        self.economy.create_account("user1")

        account = self.economy.get_account("user1")

        self.assertIsNotNone(account)
        self.assertEqual(account.address, "user1")

    def test_deposit(self):
        tx = self.economy.deposit("user1", 500.0)

        self.assertEqual(tx.tx_type, TransactionType.DEPOSIT)
        self.assertEqual(tx.amount, 500.0)

        account = self.economy.get_account("user1")
        self.assertEqual(account.balance, 500.0)

    def test_withdraw_success(self):
        self.economy.deposit("user1", 500.0)

        tx = self.economy.withdraw("user1", 200.0)

        self.assertEqual(tx.tx_type, TransactionType.WITHDRAW)
        self.assertEqual(tx.amount, 200.0)

        account = self.economy.get_account("user1")
        self.assertEqual(account.balance, 300.0)

    def test_withdraw_insufficient_balance(self):
        self.economy.deposit("user1", 100.0)

        with self.assertRaises(ValueError):
            self.economy.withdraw("user1", 200.0)

    def test_stake_tokens(self):
        self.economy.deposit("user1", 500.0)

        success, tx = self.economy.stake("user1", 100.0)

        self.assertTrue(success)
        self.assertEqual(tx.tx_type, TransactionType.STAKE)

        account = self.economy.get_account("user1")
        self.assertEqual(account.balance, 400.0)
        self.assertEqual(account.staked, 100.0)

    def test_create_task_payment(self):
        self.economy.deposit("user1", 1000.0)

        resources = ResourceMetrics(cpu_seconds=100.0)

        payment = self.economy.create_task_payment(
            task_id="task1",
            requester="user1",
            total_budget=100.0,
            resources=resources,
        )

        self.assertEqual(payment["task_id"], "task1")
        self.assertEqual(payment["requester"], "user1")
        self.assertEqual(payment["status"], "pending")

        account = self.economy.get_account("user1")
        self.assertEqual(account.locked, 100.0)

    def test_reward_worker(self):
        self.economy.deposit("requester", 1000.0)

        resources = ResourceMetrics(cpu_seconds=100.0)
        self.economy.create_task_payment(
            task_id="task1",
            requester="requester",
            total_budget=100.0,
            resources=resources,
        )

        actual_resources = ResourceMetrics(cpu_seconds=50.0)
        reward, tx = self.economy.reward_worker(
            task_id="task1",
            worker_address="worker1",
            actual_resources=actual_resources,
            quality_score=1.0,
        )

        self.assertGreater(reward, 0)
        self.assertEqual(tx.tx_type, TransactionType.REWARD)

        worker = self.economy.get_account("worker1")
        self.assertGreater(worker.balance, 0)
        self.assertGreater(worker.reputation, 50.0)

    def test_reward_worker_with_quality_score(self):
        self.economy.deposit("requester", 1000.0)

        resources = ResourceMetrics(cpu_seconds=100.0)
        self.economy.create_task_payment(
            task_id="task1",
            requester="requester",
            total_budget=100.0,
            resources=resources,
        )

        actual_resources = ResourceMetrics(cpu_seconds=50.0)
        reward_full, _ = self.economy.reward_worker(
            task_id="task1",
            worker_address="worker1",
            actual_resources=actual_resources,
            quality_score=1.0,
        )

        self.economy.create_task_payment(
            task_id="task2",
            requester="requester",
            total_budget=100.0,
            resources=resources,
        )

        reward_half, _ = self.economy.reward_worker(
            task_id="task2",
            worker_address="worker2",
            actual_resources=actual_resources,
            quality_score=0.5,
        )

        self.assertGreater(reward_full, reward_half)

    def test_penalize_worker(self):
        self.economy.deposit("worker1", 500.0)
        self.economy.stake("worker1", 100.0)

        penalty, tx = self.economy.penalize_worker(
            task_id="task1",
            worker_address="worker1",
            reason="task failed",
        )

        self.assertGreater(penalty, 0)
        self.assertEqual(tx.tx_type, TransactionType.PENALTY)

        worker = self.economy.get_account("worker1")
        self.assertLess(worker.staked, 100.0)
        self.assertLess(worker.reputation, 50.0)

    def test_finalize_task(self):
        self.economy.deposit("requester", 1000.0)

        resources = ResourceMetrics(cpu_seconds=100.0)
        self.economy.create_task_payment(
            task_id="task1",
            requester="requester",
            total_budget=100.0,
            resources=resources,
        )

        actual_resources = ResourceMetrics(cpu_seconds=30.0)
        self.economy.reward_worker(
            task_id="task1",
            worker_address="worker1",
            actual_resources=actual_resources,
        )

        result = self.economy.finalize_task("task1")

        self.assertEqual(result["status"], "completed")

        requester = self.economy.get_account("requester")
        self.assertEqual(requester.locked, 0.0)

    def test_get_balance(self):
        self.economy.deposit("user1", 500.0)

        balance = self.economy.get_balance("user1")

        self.assertEqual(balance, 500.0)

    def test_get_transaction_history(self):
        self.economy.deposit("user1", 500.0)
        self.economy.withdraw("user1", 100.0)

        history = self.economy.get_transaction_history("user1")

        self.assertEqual(len(history), 2)

    def test_get_stats(self):
        self.economy.deposit("user1", 500.0)
        self.economy.deposit("user2", 300.0)

        stats = self.economy.get_stats()

        self.assertEqual(stats["token_symbol"], "CMP")
        self.assertEqual(stats["total_accounts"], 3)
        self.assertIn("pricing", stats)


class TestIntegration(unittest.TestCase):
    """Integration tests for Token Economy."""

    def setUp(self):
        self.economy = TokenEconomy()

    def test_full_task_workflow(self):
        self.economy.deposit("requester", 1000.0)
        self.economy.deposit("worker1", 200.0)
        self.economy.stake("worker1", 100.0)

        resources = self.economy.pricing.estimate_resources(
            task_complexity="medium",
            estimated_duration=60.0,
        )

        payment = self.economy.create_task_payment(
            task_id="task1",
            requester="requester",
            total_budget=50.0,
            resources=resources,
        )

        self.assertEqual(payment["status"], "pending")

        actual_resources = ResourceMetrics(cpu_seconds=60.0)
        reward, _ = self.economy.reward_worker(
            task_id="task1",
            worker_address="worker1",
            actual_resources=actual_resources,
            quality_score=1.0,
        )

        self.assertGreater(reward, 0)

        result = self.economy.finalize_task("task1")
        self.assertEqual(result["status"], "completed")

        worker = self.economy.get_account("worker1")
        self.assertGreater(worker.balance, 100.0)
        self.assertGreater(worker.reputation, 50.0)
        self.assertEqual(worker.tasks_completed, 1)

    def test_penalty_workflow(self):
        self.economy.deposit("worker1", 500.0)
        self.economy.stake("worker1", 100.0)

        initial_stake = self.economy.get_account("worker1").staked

        penalty, _ = self.economy.penalize_worker(
            task_id="task1",
            worker_address="worker1",
            reason="malicious behavior",
            penalty_percentage=0.2,
        )

        self.assertGreater(penalty, 0)

        worker = self.economy.get_account("worker1")
        self.assertLess(worker.staked, initial_stake)
        self.assertLess(worker.reputation, 50.0)

    def test_congestion_pricing_impact(self):
        resources = ResourceMetrics(cpu_seconds=100.0)

        low_congestion_price = self.economy.pricing.calculate_price(resources)

        self.economy.pricing.update_congestion(demand=1000.0, supply=100.0)

        high_congestion_price = self.economy.pricing.calculate_price(resources)

        self.assertGreater(high_congestion_price, low_congestion_price)


class TestUptimeReward(unittest.TestCase):
    """Test node uptime reward functionality."""

    def setUp(self):
        self.economy = TokenEconomy()

    def test_calculate_uptime_reward_minimum(self):
        reward = self.economy.calculate_uptime_reward(node_id="node1", uptime_seconds=30)
        self.assertEqual(reward, 0.0)

    def test_calculate_uptime_reward_one_minute(self):
        reward = self.economy.calculate_uptime_reward(node_id="node1", uptime_seconds=60)
        self.assertGreater(reward, 0.0)

    def test_calculate_uptime_reward_with_capacity(self):
        reward_basic = self.economy.calculate_uptime_reward(
            node_id="node1", uptime_seconds=120, capacity={"cpu": 1.0, "memory": 1024}
        )

        reward_high = self.economy.calculate_uptime_reward(
            node_id="node2", uptime_seconds=120, capacity={"cpu": 8.0, "memory": 16384}
        )

        self.assertGreater(reward_high, reward_basic)

    def test_reward_node_uptime_success(self):
        success, result = self.economy.reward_node_uptime(
            node_id="node1", uptime_seconds=120, capacity={"cpu": 4.0, "memory": 8192}
        )

        self.assertTrue(success)
        self.assertIn("amount", result)
        self.assertGreater(result["amount"], 0)
        self.assertIn("tx_id", result)

    def test_reward_node_uptime_too_short(self):
        success, result = self.economy.reward_node_uptime(node_id="node1", uptime_seconds=30)

        self.assertFalse(success)
        self.assertIn("error", result)

    def test_uptime_reward_increases_balance(self):
        self.economy.reward_node_uptime(
            node_id="node1", uptime_seconds=300, capacity={"cpu": 4.0, "memory": 8192}
        )

        balance = self.economy.get_balance("node1")
        self.assertGreater(balance, 0)

    def test_uptime_reward_increases_reputation(self):
        self.economy.reward_node_uptime(
            node_id="node1", uptime_seconds=300, capacity={"cpu": 4.0, "memory": 8192}
        )

        account = self.economy.get_account("node1")
        self.assertGreater(account.reputation, 50.0)

    def test_get_node_earnings(self):
        self.economy.reward_node_uptime(
            node_id="node1", uptime_seconds=300, capacity={"cpu": 4.0, "memory": 8192}
        )

        earnings = self.economy.get_node_earnings("node1")

        self.assertIn("balance", earnings)
        self.assertIn("uptime_rewards", earnings)
        self.assertIn("reputation", earnings)
        self.assertGreater(earnings["uptime_rewards"], 0)

    def test_multiple_uptime_rewards(self):
        for _i in range(3):
            self.economy.reward_node_uptime(
                node_id="node1", uptime_seconds=120, capacity={"cpu": 4.0, "memory": 8192}
            )

        earnings = self.economy.get_node_earnings("node1")
        self.assertGreater(earnings["uptime_rewards"], 0)

        history = self.economy.get_transaction_history("node1")
        reward_txs = [tx for tx in history if tx.tx_type == TransactionType.REWARD]
        self.assertEqual(len(reward_txs), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)

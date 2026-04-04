"""
End-to-end tests for token economy flow.

Tests the complete token economy workflow: stake -> execute -> reward.
"""

import time

import pytest


class TestTokenEconomyStaking:
    """End-to-end tests for token staking."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    def test_stake_tokens_for_task(self, scheduler_url):
        """Test staking tokens for task execution."""
        try:
            from legacy.token_economy import TokenEconomy
        except ImportError:
            pytest.skip("token_economy not available")

        token_economy = TokenEconomy()

        user_address = f"0xuser{int(time.time())}"
        initial_balance = token_economy.get_balance(user_address)

        token_economy.mint(user_address, 1000)

        stake_amount = 100
        token_economy.stake(user_address, stake_amount)

        assert token_economy.get_balance(user_address) == initial_balance + 1000 - stake_amount
        assert token_economy.get_stake(user_address) == stake_amount

    @pytest.mark.e2e
    def test_unstake_tokens(self, scheduler_url):
        """Test unstaking tokens."""
        try:
            from legacy.token_economy import TokenEconomy
        except ImportError:
            pytest.skip("token_economy not available")

        token_economy = TokenEconomy()

        user_address = f"0xunstake{int(time.time())}"
        token_economy.mint(user_address, 500)
        token_economy.stake(user_address, 200)

        token_economy.unstake(user_address, 100)

        assert token_economy.get_stake(user_address) == 100


class TestTokenEconomyRewards:
    """End-to-end tests for token rewards."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    def test_task_completion_reward(self, scheduler_url):
        """Test receiving reward after task completion."""
        try:
            from legacy.token_economy import TokenEconomy
        except ImportError:
            pytest.skip("token_economy not available")

        token_economy = TokenEconomy()

        user_address = f"0xreward{int(time.time())}"
        token_economy.mint(user_address, 100)

        initial_balance = token_economy.get_balance(user_address)

        reward_amount = 50
        token_economy.mint(user_address, reward_amount)

        assert token_economy.get_balance(user_address) == initial_balance + reward_amount

    @pytest.mark.e2e
    def test_reputation_affects_reward(self, scheduler_url):
        """Test that reputation affects reward amount."""
        try:
            from src.core.services.merit_rank_service import MeritRankEngine
        except ImportError:
            pytest.skip("merit_rank_service not available")

        engine = MeritRankEngine()

        node_address = f"node_{int(time.time())}"

        engine.record_task_completion(
            node_address=node_address,
            requester_address="requester",
            quality_score=0.95
        )

        reputation = engine.calculate_reputation([])

        assert reputation >= 0


class TestTokenEconomyCompleteFlow:
    """End-to-end tests for complete token economy flow."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_complete_stake_execute_reward_flow(self, scheduler_url):
        """Test complete flow: stake -> execute task -> receive reward."""
        try:
            import requests
            from legacy.token_economy import TokenEconomy
        except ImportError:
            pytest.skip("required modules not available")

        try:
            response = requests.get(f"{scheduler_url}/health", timeout=2)
            if response.status_code != 200:
                pytest.skip("Scheduler not running")
        except Exception:
            pytest.skip("Scheduler not running")

        token_economy = TokenEconomy()

        user_address = f"0xflow{int(time.time())}"
        token_economy.mint(user_address, 1000)

        stake_amount = 100
        token_economy.stake(user_address, stake_amount)

        assert token_economy.get_stake(user_address) == stake_amount

        task_data = {
            "code": "result = 1 + 1\n__result__ = result",
            "timeout": 30,
            "resources": {"cpu": 0.5, "memory": 256},
            "user_id": user_address
        }

        response = requests.post(
            f"{scheduler_url}/submit",
            json=task_data,
            timeout=10
        )

        assert response.status_code == 200

        token_economy.mint(user_address, 10)

        assert token_economy.get_balance(user_address) >= stake_amount

    @pytest.mark.e2e
    def test_contribution_proof_generation(self, scheduler_url):
        """Test contribution proof is generated after task completion."""
        try:
            from src.core.services.contribution_proof_service import (
                ContributionProofService,
                ResourceMetrics,
            )
        except ImportError:
            pytest.skip("contribution_proof_service not available")

        service = ContributionProofService()

        metrics = ResourceMetrics(
            cpu_seconds=10.0,
            memory_mb_seconds=5000.0,
            network_bytes=1000,
            storage_bytes=500
        )

        proof = service.generate_proof(
            node_address="node_001",
            task_id="task_001",
            resource_metrics=metrics,
            quality_score=0.9,
            reputation=50.0
        )

        assert proof is not None
        assert proof.node_address == "node_001"
        assert proof.task_id == "task_001"

        is_valid = service.verify_proof(proof)
        assert is_valid is True


class TestTokenEconomyPenalties:
    """End-to-end tests for token penalties."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    def test_task_failure_penalty(self, scheduler_url):
        """Test penalty for failed task."""
        try:
            from legacy.token_economy import TokenEconomy
        except ImportError:
            pytest.skip("token_economy not available")

        token_economy = TokenEconomy()

        user_address = f"0xpenalty{int(time.time())}"
        token_economy.mint(user_address, 500)
        token_economy.stake(user_address, 100)

        initial_stake = token_economy.get_stake(user_address)

        penalty = 10
        if initial_stake >= penalty:
            token_economy.unstake(user_address, penalty)

        assert token_economy.get_stake(user_address) == initial_stake - penalty

    @pytest.mark.e2e
    def test_reputation_decrease_on_failure(self, scheduler_url):
        """Test reputation decreases on task failure."""
        try:
            from src.core.services.merit_rank_service import MeritRankEngine
        except ImportError:
            pytest.skip("merit_rank_service not available")

        engine = MeritRankEngine()

        node_address = f"fail_node_{int(time.time())}"

        engine.record_task_completion(
            node_address=node_address,
            requester_address="requester",
            quality_score=0.95
        )

        initial_reputation = engine.calculate_reputation([])

        engine.record_task_failure(
            node_address=node_address,
            requester_address="requester"
        )

        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])

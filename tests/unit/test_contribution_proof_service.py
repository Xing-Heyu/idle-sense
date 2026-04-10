"""
贡献证明服务单元测试

测试覆盖:
- 贡献证明生成
- 签名验证
- 贡献分计算
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.core.services.contribution_proof_service import (
    ContributionProof,
    ContributionProofService,
    ResourceMetrics,
)


class TestResourceMetrics(unittest.TestCase):
    """测试资源度量数据类"""

    def test_resource_metrics_creation(self):
        metrics = ResourceMetrics(
            cpu_seconds=100.0, memory_gb_seconds=50.0, storage_gb=10.0, network_gb=5.0
        )

        self.assertEqual(metrics.cpu_seconds, 100.0)
        self.assertEqual(metrics.memory_gb_seconds, 50.0)
        self.assertEqual(metrics.storage_gb, 10.0)
        self.assertEqual(metrics.network_gb, 5.0)

    def test_resource_metrics_defaults(self):
        metrics = ResourceMetrics()

        self.assertEqual(metrics.cpu_seconds, 0.0)
        self.assertEqual(metrics.memory_gb_seconds, 0.0)
        self.assertEqual(metrics.storage_gb, 0.0)
        self.assertEqual(metrics.network_gb, 0.0)

    def test_resource_metrics_to_dict(self):
        metrics = ResourceMetrics(cpu_seconds=100.0, memory_gb_seconds=50.0)

        data = metrics.to_dict()

        self.assertEqual(data["cpu_seconds"], 100.0)
        self.assertEqual(data["memory_gb_seconds"], 50.0)
        self.assertEqual(data["storage_gb"], 0.0)
        self.assertEqual(data["network_gb"], 0.0)

    def test_resource_metrics_from_dict(self):
        data = {
            "cpu_seconds": 200.0,
            "memory_gb_seconds": 100.0,
            "storage_gb": 20.0,
            "network_gb": 10.0,
        }

        metrics = ResourceMetrics.from_dict(data)

        self.assertEqual(metrics.cpu_seconds, 200.0)
        self.assertEqual(metrics.memory_gb_seconds, 100.0)
        self.assertEqual(metrics.storage_gb, 20.0)
        self.assertEqual(metrics.network_gb, 10.0)

    def test_resource_metrics_roundtrip(self):
        original = ResourceMetrics(
            cpu_seconds=150.0, memory_gb_seconds=75.0, storage_gb=15.0, network_gb=8.0
        )

        data = original.to_dict()
        restored = ResourceMetrics.from_dict(data)

        self.assertEqual(restored.cpu_seconds, original.cpu_seconds)
        self.assertEqual(restored.memory_gb_seconds, original.memory_gb_seconds)
        self.assertEqual(restored.storage_gb, original.storage_gb)
        self.assertEqual(restored.network_gb, original.network_gb)


class TestContributionProofDataclass(unittest.TestCase):
    """测试贡献证明数据类"""

    def test_contribution_proof_creation(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)
        proof = ContributionProof(
            proof_id="proof-001",
            node_address="node1",
            task_id="task1",
            resource_metrics=metrics,
            quality_score=1.0,
            complexity_coefficient=1.5,
            reputation_bonus=1.0,
            contribution_score=150.0,
            timestamp=time.time(),
        )

        self.assertEqual(proof.proof_id, "proof-001")
        self.assertEqual(proof.node_address, "node1")
        self.assertEqual(proof.task_id, "task1")
        self.assertEqual(proof.contribution_score, 150.0)

    def test_contribution_proof_defaults(self):
        metrics = ResourceMetrics()
        proof = ContributionProof(
            proof_id="proof-001",
            node_address="node1",
            task_id="task1",
            resource_metrics=metrics,
            quality_score=1.0,
            complexity_coefficient=1.0,
            reputation_bonus=1.0,
            contribution_score=0.0,
            timestamp=time.time(),
        )

        self.assertIsNone(proof.verifier_address)
        self.assertFalse(proof.verified)
        self.assertIsNone(proof.signature)

    def test_contribution_proof_to_dict(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)
        proof = ContributionProof(
            proof_id="proof-001",
            node_address="node1",
            task_id="task1",
            resource_metrics=metrics,
            quality_score=1.0,
            complexity_coefficient=1.5,
            reputation_bonus=1.0,
            contribution_score=150.0,
            timestamp=1234567890.0,
            verifier_address="verifier1",
            verified=True,
            signature="abc123",
        )

        data = proof.to_dict()

        self.assertEqual(data["proof_id"], "proof-001")
        self.assertEqual(data["node_address"], "node1")
        self.assertEqual(data["task_id"], "task1")
        self.assertEqual(data["quality_score"], 1.0)
        self.assertEqual(data["complexity_coefficient"], 1.5)
        self.assertEqual(data["reputation_bonus"], 1.0)
        self.assertEqual(data["contribution_score"], 150.0)
        self.assertEqual(data["timestamp"], 1234567890.0)
        self.assertEqual(data["verifier_address"], "verifier1")
        self.assertTrue(data["verified"])
        self.assertEqual(data["signature"], "abc123")

    def test_contribution_proof_from_dict(self):
        data = {
            "proof_id": "proof-002",
            "node_address": "node2",
            "task_id": "task2",
            "resource_metrics": {
                "cpu_seconds": 200.0,
                "memory_gb_seconds": 100.0,
                "storage_gb": 0.0,
                "network_gb": 0.0,
            },
            "quality_score": 0.8,
            "complexity_coefficient": 2.0,
            "reputation_bonus": 1.2,
            "contribution_score": 300.0,
            "timestamp": 1234567890.0,
            "verifier_address": "verifier2",
            "verified": True,
            "signature": "def456",
        }

        proof = ContributionProof.from_dict(data)

        self.assertEqual(proof.proof_id, "proof-002")
        self.assertEqual(proof.node_address, "node2")
        self.assertEqual(proof.task_id, "task2")
        self.assertEqual(proof.quality_score, 0.8)
        self.assertEqual(proof.complexity_coefficient, 2.0)
        self.assertEqual(proof.reputation_bonus, 1.2)
        self.assertEqual(proof.contribution_score, 300.0)
        self.assertEqual(proof.resource_metrics.cpu_seconds, 200.0)

    def test_contribution_proof_roundtrip(self):
        metrics = ResourceMetrics(cpu_seconds=300.0, memory_gb_seconds=150.0)
        original = ContributionProof(
            proof_id="proof-003",
            node_address="node3",
            task_id="task3",
            resource_metrics=metrics,
            quality_score=0.9,
            complexity_coefficient=1.8,
            reputation_bonus=1.1,
            contribution_score=500.0,
            timestamp=time.time(),
            verified=True,
            signature="sig789",
        )

        data = original.to_dict()
        restored = ContributionProof.from_dict(data)

        self.assertEqual(restored.proof_id, original.proof_id)
        self.assertEqual(restored.node_address, original.node_address)
        self.assertEqual(restored.task_id, original.task_id)
        self.assertEqual(restored.quality_score, original.quality_score)
        self.assertEqual(restored.contribution_score, original.contribution_score)


class TestContributionProofGeneration(unittest.TestCase):
    """测试贡献证明生成"""

    def setUp(self):
        self.service = ContributionProofService()

    def test_generate_proof_basic(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)
        proof = self.service.generate_proof(
            node_address="node1", task_id="task1", resource_metrics=metrics
        )

        self.assertIsNotNone(proof.proof_id)
        self.assertEqual(proof.node_address, "node1")
        self.assertEqual(proof.task_id, "task1")
        self.assertIsNotNone(proof.signature)

    def test_generate_proof_with_quality_score(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)

        proof_high = self.service.generate_proof(
            node_address="node1", task_id="task1", resource_metrics=metrics, quality_score=1.0
        )

        proof_low = self.service.generate_proof(
            node_address="node2", task_id="task2", resource_metrics=metrics, quality_score=0.5
        )

        self.assertGreater(proof_high.contribution_score, proof_low.contribution_score)

    def test_generate_proof_with_reputation(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)

        proof_high_rep = self.service.generate_proof(
            node_address="node1", task_id="task1", resource_metrics=metrics, reputation=90.0
        )

        proof_low_rep = self.service.generate_proof(
            node_address="node2", task_id="task2", resource_metrics=metrics, reputation=30.0
        )

        self.assertGreater(proof_high_rep.reputation_bonus, proof_low_rep.reputation_bonus)

    def test_generate_proof_with_complexity(self):
        metrics_simple = ResourceMetrics(cpu_seconds=10.0)
        metrics_complex = ResourceMetrics(cpu_seconds=10.0)

        proof_simple = self.service.generate_proof(
            node_address="node1",
            task_id="task1",
            resource_metrics=metrics_simple,
            code_length=100,
            dependencies=1,
        )

        proof_complex = self.service.generate_proof(
            node_address="node2",
            task_id="task2",
            resource_metrics=metrics_complex,
            code_length=5000,
            dependencies=20,
        )

        self.assertGreater(
            proof_complex.complexity_coefficient, proof_simple.complexity_coefficient
        )

    def test_generate_proof_unique_ids(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)

        proof1 = self.service.generate_proof(
            node_address="node1", task_id="task1", resource_metrics=metrics
        )

        proof2 = self.service.generate_proof(
            node_address="node1", task_id="task2", resource_metrics=metrics
        )

        self.assertNotEqual(proof1.proof_id, proof2.proof_id)

    def test_generate_proof_timestamp(self):
        before = time.time()
        metrics = ResourceMetrics(cpu_seconds=100.0)
        proof = self.service.generate_proof(
            node_address="node1", task_id="task1", resource_metrics=metrics
        )
        after = time.time()

        self.assertGreaterEqual(proof.timestamp, before)
        self.assertLessEqual(proof.timestamp, after)


class TestSignatureVerification(unittest.TestCase):
    """测试签名验证"""

    def setUp(self):
        self.service = ContributionProofService()

    def test_verify_valid_signature(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)
        proof = self.service.generate_proof(
            node_address="node1", task_id="task1", resource_metrics=metrics
        )

        self.assertTrue(self.service.verify_proof(proof))

    def test_verify_proof_by_id(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)
        proof = self.service.generate_proof(
            node_address="node1", task_id="task1", resource_metrics=metrics
        )

        self.assertTrue(self.service.verify_proof_by_id(proof.proof_id))

    def test_verify_invalid_signature(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)
        proof = self.service.generate_proof(
            node_address="node1", task_id="task1", resource_metrics=metrics
        )

        proof.signature = "tampered_signature"

        self.assertFalse(self.service.verify_proof(proof))

    def test_verify_missing_signature(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)
        proof = self.service.generate_proof(
            node_address="node1", task_id="task1", resource_metrics=metrics
        )

        proof.signature = None

        self.assertFalse(self.service.verify_proof(proof))

    def test_verify_nonexistent_proof(self):
        self.assertFalse(self.service.verify_proof_by_id("nonexistent_id"))

    def test_different_services_different_signatures(self):
        service1 = ContributionProofService(secret_key="key1")
        service2 = ContributionProofService(secret_key="key2")

        metrics = ResourceMetrics(cpu_seconds=100.0)
        proof = service1.generate_proof(
            node_address="node1", task_id="task1", resource_metrics=metrics
        )

        self.assertTrue(service1.verify_proof(proof))
        self.assertFalse(service2.verify_proof(proof))


class TestContributionScoreCalculation(unittest.TestCase):
    """测试贡献分计算"""

    def setUp(self):
        self.service = ContributionProofService()

    def test_calculate_contribution_score_basic(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)
        score = self.service.calculate_contribution_score(metrics)

        self.assertGreater(score, 0)

    def test_calculate_contribution_score_with_memory(self):
        metrics_cpu_only = ResourceMetrics(cpu_seconds=100.0)
        metrics_with_memory = ResourceMetrics(cpu_seconds=100.0, memory_gb_seconds=50.0)

        score_cpu = self.service.calculate_contribution_score(metrics_cpu_only)
        score_with_memory = self.service.calculate_contribution_score(metrics_with_memory)

        self.assertGreater(score_with_memory, score_cpu)

    def test_calculate_contribution_score_with_quality(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)

        score_high = self.service.calculate_contribution_score(metrics, quality_score=1.0)
        score_low = self.service.calculate_contribution_score(metrics, quality_score=0.5)

        self.assertGreater(score_high, score_low)

    def test_calculate_contribution_score_with_complexity(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)

        score_simple = self.service.calculate_contribution_score(
            metrics, complexity_coefficient=1.0
        )
        score_complex = self.service.calculate_contribution_score(
            metrics, complexity_coefficient=2.0
        )

        self.assertGreater(score_complex, score_simple)

    def test_calculate_contribution_score_with_reputation(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)

        score_low_rep = self.service.calculate_contribution_score(metrics, reputation=30.0)
        score_high_rep = self.service.calculate_contribution_score(metrics, reputation=90.0)

        self.assertGreater(score_high_rep, score_low_rep)

    def test_calculate_contribution_score_zero_resources(self):
        metrics = ResourceMetrics()
        score = self.service.calculate_contribution_score(metrics)

        self.assertEqual(score, 0.0)

    def test_complexity_coefficient_calculation(self):
        coefficient = self.service._calculate_complexity_coefficient(
            code_length=1000, dependencies=10, cpu_seconds=100.0, memory_mb=1000.0
        )

        self.assertGreater(coefficient, 1.0)

    def test_complexity_coefficient_max(self):
        coefficient = self.service._calculate_complexity_coefficient(
            code_length=100000, dependencies=1000, cpu_seconds=10000.0, memory_mb=100000.0
        )

        self.assertLessEqual(coefficient, 10.0)

    def test_reputation_bonus_high(self):
        bonus = self.service._calculate_reputation_bonus(90.0)

        self.assertGreater(bonus, 1.0)
        self.assertLessEqual(bonus, 1.5)

    def test_reputation_bonus_low(self):
        bonus = self.service._calculate_reputation_bonus(30.0)

        self.assertLess(bonus, 1.0)
        self.assertGreaterEqual(bonus, 0.5)

    def test_reputation_bonus_bounds(self):
        bonus_very_high = self.service._calculate_reputation_bonus(200.0)
        bonus_very_low = self.service._calculate_reputation_bonus(-100.0)

        self.assertLessEqual(bonus_very_high, 1.5)
        self.assertGreaterEqual(bonus_very_low, 0.5)


class TestProofManagement(unittest.TestCase):
    """测试证明管理"""

    def setUp(self):
        self.service = ContributionProofService()

    def test_get_proof(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)
        proof = self.service.generate_proof(
            node_address="node1", task_id="task1", resource_metrics=metrics
        )

        retrieved = self.service.get_proof(proof.proof_id)

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.proof_id, proof.proof_id)

    def test_get_nonexistent_proof(self):
        retrieved = self.service.get_proof("nonexistent_id")

        self.assertIsNone(retrieved)

    def test_get_node_proofs(self):
        for i in range(5):
            metrics = ResourceMetrics(cpu_seconds=100.0 * i)
            self.service.generate_proof(
                node_address="node1", task_id=f"task{i}", resource_metrics=metrics
            )

        proofs = self.service.get_node_proofs("node1")

        self.assertEqual(len(proofs), 5)

    def test_get_node_proofs_limit(self):
        for i in range(20):
            metrics = ResourceMetrics(cpu_seconds=100.0)
            self.service.generate_proof(
                node_address="node1", task_id=f"task{i}", resource_metrics=metrics
            )

        proofs = self.service.get_node_proofs("node1", limit=10)

        self.assertEqual(len(proofs), 10)

    def test_get_node_proofs_sorted_by_timestamp(self):
        for i in range(3):
            time.sleep(0.01)
            metrics = ResourceMetrics(cpu_seconds=100.0)
            self.service.generate_proof(
                node_address="node1", task_id=f"task{i}", resource_metrics=metrics
            )

        proofs = self.service.get_node_proofs("node1")

        self.assertGreater(proofs[0].timestamp, proofs[1].timestamp)
        self.assertGreater(proofs[1].timestamp, proofs[2].timestamp)

    def test_add_verification(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)
        proof = self.service.generate_proof(
            node_address="node1", task_id="task1", resource_metrics=metrics
        )

        result = self.service.add_verification(proof.proof_id, "verifier1")

        self.assertTrue(result)
        self.assertTrue(proof.verified)
        self.assertEqual(proof.verifier_address, "verifier1")

    def test_add_verification_nonexistent_proof(self):
        result = self.service.add_verification("nonexistent_id", "verifier1")

        self.assertFalse(result)

    def test_get_node_total_contribution(self):
        for i in range(3):
            metrics = ResourceMetrics(cpu_seconds=100.0)
            self.service.generate_proof(
                node_address="node1", task_id=f"task{i}", resource_metrics=metrics
            )

        total = self.service.get_node_total_contribution("node1")

        self.assertGreater(total, 0)

    def test_get_node_total_contribution_nonexistent(self):
        total = self.service.get_node_total_contribution("nonexistent_node")

        self.assertEqual(total, 0.0)


class TestContributionProofStats(unittest.TestCase):
    """测试统计功能"""

    def setUp(self):
        self.service = ContributionProofService()

    def test_empty_stats(self):
        stats = self.service.get_stats()

        self.assertEqual(stats["total_proofs"], 0)
        self.assertEqual(stats["verified_proofs"], 0)
        self.assertEqual(stats["total_nodes"], 0)

    def test_stats_with_proofs(self):
        for i in range(5):
            metrics = ResourceMetrics(cpu_seconds=100.0)
            self.service.generate_proof(
                node_address=f"node{i}", task_id=f"task{i}", resource_metrics=metrics
            )

        stats = self.service.get_stats()

        self.assertEqual(stats["total_proofs"], 5)
        self.assertEqual(stats["total_nodes"], 5)
        self.assertGreater(stats["total_contribution"], 0)

    def test_stats_verified_count(self):
        metrics = ResourceMetrics(cpu_seconds=100.0)
        proof = self.service.generate_proof(
            node_address="node1", task_id="task1", resource_metrics=metrics
        )

        self.service.add_verification(proof.proof_id, "verifier1")

        stats = self.service.get_stats()

        self.assertEqual(stats["verified_proofs"], 1)
        self.assertEqual(stats["unverified_proofs"], 0)

    def test_stats_avg_contribution(self):
        for i in range(3):
            metrics = ResourceMetrics(cpu_seconds=100.0)
            self.service.generate_proof(
                node_address="node1", task_id=f"task{i}", resource_metrics=metrics
            )

        stats = self.service.get_stats()

        self.assertIn("avg_contribution_per_node", stats)
        self.assertGreater(stats["avg_contribution_per_node"], 0)


class TestSecretKeyManagement(unittest.TestCase):
    """测试密钥管理"""

    def test_custom_secret_key(self):
        service = ContributionProofService(secret_key="my_secret_key")

        self.assertIsNotNone(service._secret_key)

    def test_default_secret_key_generated(self):
        service1 = ContributionProofService()
        service2 = ContributionProofService()

        self.assertNotEqual(service1._secret_key, service2._secret_key)

    def test_same_secret_key_validates_cross_service(self):
        service1 = ContributionProofService(secret_key="shared_key")
        service2 = ContributionProofService(secret_key="shared_key")

        metrics = ResourceMetrics(cpu_seconds=100.0)
        proof = service1.generate_proof(
            node_address="node1", task_id="task1", resource_metrics=metrics
        )

        self.assertTrue(service1.verify_proof(proof))
        self.assertTrue(service2.verify_proof(proof))


if __name__ == "__main__":
    unittest.main(verbosity=2)

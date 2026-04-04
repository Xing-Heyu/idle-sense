"""
贡献证明系统 (PoC)

基于论文: A proof of contribution in blockchain using game theoretical deep learning model
Wang J., arXiv 2024

核心机制:
- 贡献分 = 累计算力时长 × 任务复杂度系数 × 质量因子 × 声誉加成
- 贡献证明生成和验证
- 防篡改签名
"""

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ResourceMetrics:
    """资源使用度量"""
    cpu_seconds: float = 0.0
    memory_gb_seconds: float = 0.0
    storage_gb: float = 0.0
    network_gb: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "cpu_seconds": self.cpu_seconds,
            "memory_gb_seconds": self.memory_gb_seconds,
            "storage_gb": self.storage_gb,
            "network_gb": self.network_gb
        }

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> "ResourceMetrics":
        return cls(
            cpu_seconds=data.get("cpu_seconds", 0.0),
            memory_gb_seconds=data.get("memory_gb_seconds", 0.0),
            storage_gb=data.get("storage_gb", 0.0),
            network_gb=data.get("network_gb", 0.0)
        )


@dataclass
class ContributionProof:
    """贡献证明数据结构"""
    proof_id: str
    node_address: str
    task_id: str
    resource_metrics: ResourceMetrics
    quality_score: float
    complexity_coefficient: float
    reputation_bonus: float
    contribution_score: float
    timestamp: float
    verifier_address: Optional[str] = None
    verified: bool = False
    signature: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "node_address": self.node_address,
            "task_id": self.task_id,
            "resource_metrics": self.resource_metrics.to_dict(),
            "quality_score": self.quality_score,
            "complexity_coefficient": self.complexity_coefficient,
            "reputation_bonus": self.reputation_bonus,
            "contribution_score": self.contribution_score,
            "timestamp": self.timestamp,
            "verifier_address": self.verifier_address,
            "verified": self.verified,
            "signature": self.signature
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContributionProof":
        return cls(
            proof_id=data["proof_id"],
            node_address=data["node_address"],
            task_id=data["task_id"],
            resource_metrics=ResourceMetrics.from_dict(data["resource_metrics"]),
            quality_score=data["quality_score"],
            complexity_coefficient=data["complexity_coefficient"],
            reputation_bonus=data["reputation_bonus"],
            contribution_score=data["contribution_score"],
            timestamp=data["timestamp"],
            verifier_address=data.get("verifier_address"),
            verified=data.get("verified", False),
            signature=data.get("signature")
        )


class ContributionProofService:
    """贡献证明服务"""

    # 复杂度系数计算参数
    BASE_COMPLEXITY = 1.0
    CODE_LENGTH_WEIGHT = 0.001
    DEPENDENCY_WEIGHT = 0.1
    CPU_WEIGHT = 0.5
    MEMORY_WEIGHT = 0.0001

    # 声誉加成计算参数
    BASE_REPUTATION = 50.0
    MAX_REPUTATION_BONUS = 0.5

    def __init__(self, secret_key: Optional[str] = None):
        self._secret_key = secret_key or str(uuid.uuid4())
        self._proofs: dict[str, ContributionProof] = {}
        self._node_contributions: dict[str, float] = {}

    def _generate_proof_id(self) -> str:
        """生成唯一证明ID"""
        return str(uuid.uuid4())

    def _calculate_complexity_coefficient(
        self,
        code_length: int = 0,
        dependencies: int = 0,
        cpu_seconds: float = 0.0,
        memory_mb: float = 0.0
    ) -> float:
        """
        计算任务复杂度系数

        公式: 1.0 + (代码长度 × 0.001) + (依赖数 × 0.1) + (CPU秒 × 0.5) + (内存MB × 0.0001)
        """
        coefficient = self.BASE_COMPLEXITY
        coefficient += code_length * self.CODE_LENGTH_WEIGHT
        coefficient += dependencies * self.DEPENDENCY_WEIGHT
        coefficient += cpu_seconds * self.CPU_WEIGHT
        coefficient += memory_mb * self.MEMORY_WEIGHT
        return min(coefficient, 10.0)

    def _calculate_reputation_bonus(self, reputation: float) -> float:
        """
        计算声誉加成

        公式: 1 + ((声誉 - 50) / 100)

        范围: 0.5 - 1.5
        """
        bonus = 1.0 + ((reputation - self.BASE_REPUTATION) / 100.0)
        return max(0.5, min(1.5, bonus))

    def calculate_contribution_score(
        self,
        resource_metrics: ResourceMetrics,
        quality_score: float = 1.0,
        complexity_coefficient: float = 1.0,
        reputation: float = 50.0
    ) -> float:
        """
        计算贡献分

        公式: (CPU秒 + 内存GB秒) × 复杂度系数 × 质量因子 × 声誉加成
        """
        base_score = resource_metrics.cpu_seconds + resource_metrics.memory_gb_seconds
        reputation_bonus = self._calculate_reputation_bonus(reputation)

        contribution_score = (
            base_score *
            complexity_coefficient *
            quality_score *
            reputation_bonus
        )

        return contribution_score

    def generate_proof(
        self,
        node_address: str,
        task_id: str,
        resource_metrics: ResourceMetrics,
        quality_score: float = 1.0,
        code_length: int = 0,
        dependencies: int = 0,
        reputation: float = 50.0
    ) -> ContributionProof:
        """
        生成贡献证明

        Args:
            node_address: 节点地址
            task_id: 任务ID
            resource_metrics: 资源使用度量
            quality_score: 质量评分 (0.0-1.0)
            code_length: 代码长度
            dependencies: 依赖数量
            reputation: 节点声誉

        Returns:
            贡献证明
        """
        complexity_coefficient = self._calculate_complexity_coefficient(
            code_length=code_length,
            dependencies=dependencies,
            cpu_seconds=resource_metrics.cpu_seconds,
            memory_mb=resource_metrics.memory_gb_seconds * 1024
        )

        reputation_bonus = self._calculate_reputation_bonus(reputation)

        contribution_score = self.calculate_contribution_score(
            resource_metrics=resource_metrics,
            quality_score=quality_score,
            complexity_coefficient=complexity_coefficient,
            reputation=reputation
        )

        proof = ContributionProof(
            proof_id=self._generate_proof_id(),
            node_address=node_address,
            task_id=task_id,
            resource_metrics=resource_metrics,
            quality_score=quality_score,
            complexity_coefficient=complexity_coefficient,
            reputation_bonus=reputation_bonus,
            contribution_score=contribution_score,
            timestamp=time.time()
        )

        proof.signature = self._sign_proof(proof)
        self._proofs[proof.proof_id] = proof

        if node_address not in self._node_contributions:
            self._node_contributions[node_address] = 0.0
        self._node_contributions[node_address] += contribution_score

        return proof

    def _sign_proof(self, proof: ContributionProof) -> str:
        """签名证明数据"""
        proof_data = {
            "proof_id": proof.proof_id,
            "node_address": proof.node_address,
            "task_id": proof.task_id,
            "contribution_score": proof.contribution_score,
            "timestamp": proof.timestamp
        }
        proof_json = json.dumps(proof_data, sort_keys=True).encode()
        signature = hmac.new(
            self._secret_key.encode(),
            proof_json,
            hashlib.sha256
        ).hexdigest()
        return signature

    def verify_proof(self, proof: ContributionProof) -> bool:
        """验证贡献证明"""
        if proof.signature is None:
            return False

        expected_signature = self._sign_proof(proof)
        return hmac.compare_digest(proof.signature, expected_signature)

    def verify_proof_by_id(self, proof_id: str) -> bool:
        """通过ID验证贡献证明"""
        if proof_id not in self._proofs:
            return False
        return self.verify_proof(self._proofs[proof_id])

    def add_verification(
        self,
        proof_id: str,
        verifier_address: str
    ) -> bool:
        """
        添加验证

        Args:
            proof_id: 证明ID
            verifier_address: 验证者地址

        Returns:
            是否成功
        """
        if proof_id not in self._proofs:
            return False

        proof = self._proofs[proof_id]
        proof.verifier_address = verifier_address
        proof.verified = True
        return True

    def get_proof(self, proof_id: str) -> Optional[ContributionProof]:
        """获取贡献证明"""
        return self._proofs.get(proof_id)

    def get_node_proofs(
        self,
        node_address: str,
        limit: int = 100
    ) -> list[ContributionProof]:
        """获取节点的贡献证明列表"""
        proofs = [
            p for p in self._proofs.values()
            if p.node_address == node_address
        ]
        return sorted(proofs, key=lambda p: p.timestamp, reverse=True)[:limit]

    def get_node_total_contribution(self, node_address: str) -> float:
        """获取节点总贡献分"""
        return self._node_contributions.get(node_address, 0.0)

    def get_stats(self) -> dict[str, Any]:
        """获取贡献证明系统统计"""
        total_proofs = len(self._proofs)
        verified_proofs = sum(1 for p in self._proofs.values() if p.verified)
        total_contribution = sum(self._node_contributions.values())
        avg_contribution = (
            total_contribution / len(self._node_contributions)
            if self._node_contributions
            else 0.0
        )

        return {
            "total_proofs": total_proofs,
            "verified_proofs": verified_proofs,
            "unverified_proofs": total_proofs - verified_proofs,
            "total_nodes": len(self._node_contributions),
            "total_contribution": total_contribution,
            "avg_contribution_per_node": avg_contribution
        }


__all__ = [
    "ContributionProofService",
    "ContributionProof",
    "ResourceMetrics"
]

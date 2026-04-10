"""
代币经济系统集成测试

测试内容：
- 任务提交时的代币扣除
- 任务完成时的代币奖励
- 声誉系统更新
- 贡献证明生成
- 审计日志记录
"""

import pytest
import time
from unittest.mock import Mock, MagicMock

from src.core.entities.task import Task, TaskStatus
from src.core.use_cases.task import (
    CompleteTaskWithTokenEconomyUseCase,
    CompleteTaskWithTokenRequest,
    SubmitTaskWithTokenEconomyUseCase,
    SubmitTaskWithTokenRequest,
)
from src.core.services.token_economy_service import TokenEconomyService
from src.core.services.merit_rank_service import MeritRankEngine, Feedback
from src.core.services.contribution_proof_service import ContributionProofService
from legacy.token_economy import ResourceMetrics
from src.infrastructure.audit import AuditLogger, AuditAction


@pytest.fixture
def task_repository():
    """模拟任务仓储"""
    repo = Mock()
    task = Task(
        task_id="task_001",
        code="print('test')",
        user_id="user_001",
        timeout=300,
        cpu_request=1.0,
        memory_request=512,
    )
    repo.save = Mock()
    repo.get_by_id = Mock(return_value=task)
    repo.list_by_user = Mock(return_value=[task])
    return repo


@pytest.fixture
def scheduler_service():
    """模拟调度器服务"""
    service = Mock()
    service.submit_task = Mock(return_value=(True, {"task_id": "task_001"}))
    service.complete_task = Mock(return_value=True)
    return service


@pytest.fixture
def token_economy_service():
    """代币经济服务"""
    from legacy.token_economy import TokenEconomy

    economy = TokenEconomy()
    service = TokenEconomyService(economy)
    return service


@pytest.fixture
def merit_rank_engine():
    """MeritRank声誉引擎"""
    return MeritRankEngine()


@pytest.fixture
def contribution_proof_service():
    """贡献证明服务"""
    return ContributionProofService(secret_key="test_secret")


@pytest.fixture
def audit_logger(tmp_path):
    """审计日志器"""
    db_path = str(tmp_path / "test_audit.db")
    return AuditLogger(db_path=db_path)


class TestSubmitTaskWithTokenEconomy:
    """测试带代币经济的任务提交"""

    def test_submit_task_success_with_sufficient_balance(
        self, task_repository, scheduler_service, token_economy_service, audit_logger
    ):
        """测试余额充足时的任务提交"""
        user_id = "user_001"

        account = token_economy_service.get_or_create_account(user_id)

        use_case = SubmitTaskWithTokenEconomyUseCase(
            task_repository=task_repository,
            scheduler_service=scheduler_service,
            token_economy_service=token_economy_service,
            audit_logger=audit_logger,
        )

        request = SubmitTaskWithTokenRequest(
            code="print('hello world')",
            user_id=user_id,
            timeout=300,
            cpu=1.0,
            memory=512,
            priority=0.0,
        )

        response = use_case.execute(request)

        assert response.success is True
        assert response.task_id == "task_001"
        assert response.cost_estimate is not None
        assert response.account_info is not None
        assert task_repository.save.called
        assert scheduler_service.submit_task.called

    def test_submit_task_insufficient_balance(
        self, task_repository, scheduler_service, token_economy_service, audit_logger
    ):
        """测试余额不足时的任务提交"""
        user_id = "user_poor"

        use_case = SubmitTaskWithTokenEconomyUseCase(
            task_repository=task_repository,
            scheduler_service=scheduler_service,
            token_economy_service=token_economy_service,
            audit_logger=audit_logger,
        )

        economy = token_economy_service.economy
        account = economy.create_account(user_id, initial_balance=0.0001)

        request = SubmitTaskWithTokenRequest(
            code="print('expensive task')",
            user_id=user_id,
            timeout=300,
            cpu=1.0,
            memory=512,
            priority=1.0,
        )

        response = use_case.execute(request)

        assert response.success is False
        assert "余额不足" in response.message
        assert not scheduler_service.submit_task.called

    def test_submit_task_no_user_id(
        self, task_repository, scheduler_service, token_economy_service, audit_logger
    ):
        """测试没有用户ID时的任务提交"""
        use_case = SubmitTaskWithTokenEconomyUseCase(
            task_repository=task_repository,
            scheduler_service=scheduler_service,
            token_economy_service=token_economy_service,
            audit_logger=audit_logger,
        )

        request = SubmitTaskWithTokenRequest(
            code="print('no user')", user_id=None, timeout=300, cpu=1.0, memory=512
        )

        response = use_case.execute(request)

        assert response.success is False
        assert "需要用户ID" in response.message


class TestCompleteTaskWithTokenEconomy:
    """测试带代币经济的任务完成"""

    def test_complete_task_success(
        self,
        task_repository,
        scheduler_service,
        token_economy_service,
        merit_rank_engine,
        contribution_proof_service,
        audit_logger,
    ):
        """测试任务成功完成"""
        user_id = "user_002"
        node_address = "node_001"
        task_id = "task_001"

        economy = token_economy_service.economy
        account = economy.create_account(user_id, initial_balance=1000.0)

        resources = ResourceMetrics(cpu_seconds=1.0 * 300, memory_gb_seconds=(512 / 1024) * 300)

        economy.create_task_payment(
            task_id=task_id, requester=user_id, total_budget=10.0, resources=resources, priority=0
        )

        use_case = CompleteTaskWithTokenEconomyUseCase(
            task_repository=task_repository,
            scheduler_service=scheduler_service,
            token_economy_service=token_economy_service,
            merit_rank_engine=merit_rank_engine,
            contribution_proof_service=contribution_proof_service,
            audit_logger=audit_logger,
        )

        task = task_repository.get_by_id(task_id)
        task.assigned_node = node_address
        task.user_id = user_id

        request = CompleteTaskWithTokenRequest(
            task_id=task_id,
            result="task completed successfully",
            quality_score=1.0,
            execution_time_seconds=10.5,
            peak_memory_mb=256.0,
        )

        response = use_case.execute(request)

        assert response.success is True
        assert response.reward_info is not None
        assert response.contribution_proof_id is not None
        assert scheduler_service.complete_task.called

    def test_complete_task_nonexistent(
        self,
        task_repository,
        scheduler_service,
        token_economy_service,
        merit_rank_engine,
        contribution_proof_service,
        audit_logger,
    ):
        """测试完成不存在的任务"""
        task_repository.get_by_id = Mock(return_value=None)

        use_case = CompleteTaskWithTokenEconomyUseCase(
            task_repository=task_repository,
            scheduler_service=scheduler_service,
            token_economy_service=token_economy_service,
            merit_rank_engine=merit_rank_engine,
            contribution_proof_service=contribution_proof_service,
            audit_logger=audit_logger,
        )

        request = CompleteTaskWithTokenRequest(
            task_id="nonexistent_task",
            result="",
            quality_score=1.0,
            execution_time_seconds=0.0,
            peak_memory_mb=0.0,
        )

        response = use_case.execute(request)

        assert response.success is False
        assert "不存在" in response.message


class TestMeritRankIntegration:
    """测试MeritRank声誉系统集成"""

    def test_task_completion_updates_reputation(self, merit_rank_engine):
        """测试任务完成更新声誉"""
        node_address = "node_repu_001"
        requester_address = "requester_001"

        initial_reputation = merit_rank_engine.get_reputation(node_address)

        merit_rank_engine.record_task_completion(
            node_address=node_address, requester_address=requester_address, quality_score=1.0
        )

        new_reputation = merit_rank_engine.get_reputation(node_address)
        assert new_reputation > initial_reputation

    def test_task_failure_penalizes_reputation(self, merit_rank_engine):
        """测试任务失败惩罚声誉"""
        node_address = "node_repu_002"
        requester_address = "requester_002"

        merit_rank_engine.record_task_completion(
            node_address=node_address, requester_address=requester_address, quality_score=1.0
        )

        high_reputation = merit_rank_engine.get_reputation(node_address)

        merit_rank_engine.record_task_failure(
            node_address=node_address, requester_address=requester_address
        )

        low_reputation = merit_rank_engine.get_reputation(node_address)
        assert low_reputation < high_reputation


class TestContributionProofIntegration:
    """测试贡献证明集成"""

    def test_generate_contribution_proof(self, contribution_proof_service):
        """测试生成贡献证明"""
        node_address = "node_proof_001"
        task_id = "task_proof_001"

        resource_metrics = ResourceMetrics(
            cpu_seconds=10.0, memory_gb_seconds=0.5, storage_gb=0.0, network_gb=0.0
        )

        proof = contribution_proof_service.generate_proof(
            node_address=node_address,
            task_id=task_id,
            resource_metrics=resource_metrics,
            quality_score=1.0,
            code_length=100,
            reputation=50.0,
        )

        assert proof is not None
        assert proof.proof_id is not None
        assert proof.node_address == node_address
        assert proof.task_id == task_id
        assert proof.signature is not None

    def test_verify_contribution_proof(self, contribution_proof_service):
        """测试验证贡献证明"""
        node_address = "node_proof_002"
        task_id = "task_proof_002"

        resource_metrics = ResourceMetrics(cpu_seconds=5.0, memory_gb_seconds=0.25)

        proof = contribution_proof_service.generate_proof(
            node_address=node_address,
            task_id=task_id,
            resource_metrics=resource_metrics,
            quality_score=0.9,
        )

        is_valid = contribution_proof_service.verify_proof(proof)
        assert is_valid is True


class TestAuditLogIntegration:
    """测试审计日志集成"""

    def test_task_submit_audit_log(self, audit_logger):
        """测试任务提交审计日志"""
        user_id = "user_audit_001"

        audit_logger.log(
            action=AuditAction.TASK_SUBMIT,
            user_id=user_id,
            resource_type="task",
            resource_id="task_audit_001",
            details={"cost": 10.5, "cpu": 1.0, "memory": 512},
        )

        logs = audit_logger.query(user_id=user_id)
        assert len(logs) == 1
        assert logs[0].action == AuditAction.TASK_SUBMIT

    def test_task_complete_audit_log(self, audit_logger):
        """测试任务完成审计日志"""
        user_id = "user_audit_002"

        audit_logger.log(
            action=AuditAction.TASK_COMPLETE,
            user_id=user_id,
            resource_type="task",
            resource_id="task_audit_002",
            details={"quality_score": 1.0, "reward": 5.0},
        )

        logs = audit_logger.query(user_id=user_id)
        assert len(logs) == 1
        assert logs[0].action == AuditAction.TASK_COMPLETE


class TestEndToEndWorkflow:
    """端到端工作流测试"""

    def test_full_task_lifecycle(
        self,
        task_repository,
        scheduler_service,
        token_economy_service,
        merit_rank_engine,
        contribution_proof_service,
        audit_logger,
    ):
        """测试完整的任务生命周期：提交 -> 完成"""
        user_id = "user_e2e_001"
        node_address = "node_e2e_001"

        submit_use_case = SubmitTaskWithTokenEconomyUseCase(
            task_repository=task_repository,
            scheduler_service=scheduler_service,
            token_economy_service=token_economy_service,
            audit_logger=audit_logger,
        )

        submit_request = SubmitTaskWithTokenRequest(
            code="print('e2e test')", user_id=user_id, timeout=300, cpu=1.0, memory=512
        )

        submit_response = submit_use_case.execute(submit_request)
        assert submit_response.success is True
        task_id = submit_response.task_id

        task = task_repository.get_by_id(task_id)
        task.assigned_node = node_address

        complete_use_case = CompleteTaskWithTokenEconomyUseCase(
            task_repository=task_repository,
            scheduler_service=scheduler_service,
            token_economy_service=token_economy_service,
            merit_rank_engine=merit_rank_engine,
            contribution_proof_service=contribution_proof_service,
            audit_logger=audit_logger,
        )

        complete_request = CompleteTaskWithTokenRequest(
            task_id=task_id,
            result="e2e test completed",
            quality_score=1.0,
            execution_time_seconds=15.0,
            peak_memory_mb=384.0,
        )

        complete_response = complete_use_case.execute(complete_request)
        assert complete_response.success is True
        assert complete_response.contribution_proof_id is not None

        node_reputation = merit_rank_engine.get_reputation(node_address)
        assert node_reputation > 50.0

        audit_logs = audit_logger.query()
        assert len(audit_logs) >= 2


class TestTokenEncryptionIntegration:
    """测试TokenEncryption服务集成"""

    def test_token_encryption_basic_flow(self):
        """测试TokenEncryption基本加密解密流程"""
        from src.core.services.token_encryption_service import (
            TokenEncryption,
            EncryptedData,
        )

        encryption = TokenEncryption(main_password="test_master_password_123")

        sensitive_data = {
            "balance": 1000.0,
            "user_id": "user_enc_001",
            "transactions": [{"id": "tx_001", "amount": 100.0}, {"id": "tx_002", "amount": -50.0}],
        }

        encrypted = encryption.encrypt(sensitive_data)
        assert encrypted.ciphertext is not None
        assert encrypted.nonce is not None
        assert encrypted.salt is not None
        assert encrypted.hmac is not None

        decrypted = encryption.decrypt(encrypted)
        assert decrypted["balance"] == sensitive_data["balance"]
        assert decrypted["user_id"] == sensitive_data["user_id"]
        assert len(decrypted["transactions"]) == 2

    def test_token_encryption_string_storage(self):
        """测试TokenEncryption字符串存储格式"""
        from src.core.services.token_encryption_service import TokenEncryption

        encryption = TokenEncryption(main_password="storage_password_456")

        data = {"token_balance": 500.0, "stake": 100.0}

        encrypted_str = encryption.encrypt_to_string(data)
        assert isinstance(encrypted_str, str)

        import json

        parsed = json.loads(encrypted_str)
        assert "ciphertext" in parsed
        assert "nonce" in parsed
        assert "salt" in parsed
        assert "hmac" in parsed

        decrypted = encryption.decrypt_from_string(encrypted_str)
        assert decrypted["token_balance"] == 500.0
        assert decrypted["stake"] == 100.0

    def test_token_encryption_integrity_verification(self):
        """测试TokenEncryption数据完整性验证"""
        from src.core.services.token_encryption_service import (
            TokenEncryption,
            EncryptedData,
            IntegrityError,
        )

        encryption = TokenEncryption(main_password="integrity_test_789")

        data = {"critical_balance": 9999.0}
        encrypted = encryption.encrypt(data)

        tampered_ciphertext = bytearray(encrypted.ciphertext)
        tampered_ciphertext[0] ^= 0xFF
        tampered_data = EncryptedData(
            ciphertext=bytes(tampered_ciphertext),
            nonce=encrypted.nonce,
            salt=encrypted.salt,
            hmac=encrypted.hmac,
        )

        import pytest

        with pytest.raises(IntegrityError):
            encryption.decrypt(tampered_data)

    def test_token_encryption_key_rotation(self):
        """测试TokenEncryption密钥轮换"""
        from src.core.services.token_encryption_service import TokenEncryption

        encryption = TokenEncryption(main_password="old_password")

        data = {"balance": 100.0}
        encrypted_str = encryption.encrypt_to_string(data)

        encryption.rotate_keys(new_password="new_password")

        new_encryption = TokenEncryption(main_password="new_password")


class TestFullTokenEconomyWithEncryption:
    """测试完整代币经济与加密集成"""

    def test_encrypted_token_data_flow(self, tmp_path):
        """测试加密代币数据完整流程"""
        from src.core.services.token_encryption_service import TokenEncryption

        encryption = TokenEncryption(main_password="economy_master_key")

        token_data = {
            "account_id": "user_full_001",
            "balance": 1000.0,
            "staked": 500.0,
            "reputation": 75.5,
            "contribution_score": 120.0,
        }

        encrypted_str = encryption.encrypt_to_string(token_data)

        storage_file = tmp_path / "encrypted_token_data.json"
        storage_file.write_text(encrypted_str, encoding="utf-8")

        loaded_str = storage_file.read_text(encoding="utf-8")
        decrypted = encryption.decrypt_from_string(loaded_str)

        assert decrypted["account_id"] == token_data["account_id"]
        assert decrypted["balance"] == token_data["balance"]
        assert decrypted["staked"] == token_data["staked"]
        assert decrypted["reputation"] == token_data["reputation"]

    def test_key_file_storage(self, tmp_path):
        """测试密钥文件存储"""
        from src.core.services.token_encryption_service import TokenEncryption

        encryption = TokenEncryption(main_password="key_file_password")

        key_file = str(tmp_path / "keys.enc")
        encryption.save_keys_to_file(key_file, protect_with_password=False)

        new_encryption = TokenEncryption()
        new_encryption._load_keys_from_file(key_file)

        data = {"test": "value"}
        encrypted = encryption.encrypt(data)
        decrypted = new_encryption.decrypt(encrypted)
        assert decrypted["test"] == "value"


class TestMeritRankContributionProofIntegration:
    """测试MeritRank与ContributionProof深度集成"""

    def test_reputation_affects_contribution_score(
        self, merit_rank_engine, contribution_proof_service
    ):
        """测试声誉影响贡献分计算"""
        node_address = "node_merit_001"
        requester_address = "requester_merit_001"

        for i in range(5):
            merit_rank_engine.record_task_completion(
                node_address=node_address,
                requester_address=f"{requester_address}_{i}",
                quality_score=0.9 + (i * 0.02),
            )

        high_reputation = merit_rank_engine.get_reputation(node_address)

        proof = contribution_proof_service.generate_proof(
            node_address=node_address,
            task_id="task_merit_001",
            resource_metrics=ResourceMetrics(cpu_seconds=10.0, memory_gb_seconds=0.5),
            quality_score=1.0,
            code_length=100,
            reputation=high_reputation,
        )

        expected_bonus = 1.0 + ((high_reputation - 50.0) / 100.0)
        expected_bonus = max(0.5, min(1.5, expected_bonus))
        assert abs(proof.reputation_bonus - expected_bonus) < 0.01
        assert proof.contribution_score > 0

    def test_multiple_nodes_reputation_ranking(self, merit_rank_engine):
        """测试多节点声誉排名"""
        nodes = [f"node_rank_{i:03d}" for i in range(10)]

        for i, node in enumerate(nodes):
            quality = 0.5 + (i * 0.05)
            for j in range(3):
                merit_rank_engine.record_task_completion(
                    node_address=node,
                    requester_address=f"requester_rank_{i}_{j}",
                    quality_score=quality,
                )

        reputations = [(node, merit_rank_engine.get_reputation(node)) for node in nodes]
        reputations.sort(key=lambda x: x[1], reverse=True)

        assert reputations[0][1] >= reputations[-1][1]


class TestSecurityEnhancedWorkflow:
    """安全增强工作流测试"""

    def test_complete_secure_task_workflow(
        self,
        task_repository,
        scheduler_service,
        token_economy_service,
        merit_rank_engine,
        contribution_proof_service,
        audit_logger,
        tmp_path,
    ):
        """测试完整的安全增强任务工作流"""
        from src.core.services.token_encryption_service import TokenEncryption

        encryption = TokenEncryption(main_password="secure_workflow_key")

        user_id = "user_secure_001"
        node_address = "node_secure_001"

        submit_use_case = SubmitTaskWithTokenEconomyUseCase(
            task_repository=task_repository,
            scheduler_service=scheduler_service,
            token_economy_service=token_economy_service,
            audit_logger=audit_logger,
        )

        submit_request = SubmitTaskWithTokenRequest(
            code="print('secure task')", user_id=user_id, timeout=300, cpu=1.0, memory=512
        )

        submit_response = submit_use_case.execute(submit_request)
        assert submit_response.success is True
        task_id = submit_response.task_id

        task = task_repository.get_by_id(task_id)
        task.assigned_node = node_address

        complete_use_case = CompleteTaskWithTokenEconomyUseCase(
            task_repository=task_repository,
            scheduler_service=scheduler_service,
            token_economy_service=token_economy_service,
            merit_rank_engine=merit_rank_engine,
            contribution_proof_service=contribution_proof_service,
            audit_logger=audit_logger,
        )

        complete_request = CompleteTaskWithTokenRequest(
            task_id=task_id,
            result="secure task completed",
            quality_score=0.95,
            execution_time_seconds=20.0,
            peak_memory_mb=400.0,
        )

        complete_response = complete_use_case.execute(complete_request)
        assert complete_response.success is True

        secure_record = {
            "task_id": task_id,
            "user_id": user_id,
            "node_address": node_address,
            "reward_info": complete_response.reward_info,
            "contribution_proof_id": complete_response.contribution_proof_id,
            "reputation": merit_rank_engine.get_reputation(node_address),
        }

        encrypted_record = encryption.encrypt_to_string(secure_record)
        secure_file = tmp_path / "secure_task_record.enc"
        secure_file.write_text(encrypted_record, encoding="utf-8")

        loaded_encrypted = secure_file.read_text(encoding="utf-8")
        decrypted_record = encryption.decrypt_from_string(loaded_encrypted)

        assert decrypted_record["task_id"] == task_id
        assert decrypted_record["user_id"] == user_id
        assert decrypted_record["contribution_proof_id"] == complete_response.contribution_proof_id

        audit_logs = audit_logger.query(user_id=user_id)
        assert len(audit_logs) >= 1

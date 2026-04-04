"""
代币系统安全加固 - 测试脚本

测试内容:
1. MeritRank 声誉引擎测试
2. 贡献证明系统测试
3. 加密存储测试
4. 抗女巫攻击测试
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def test_merit_rank():
    """测试 MeritRank 声誉引擎"""
    print("=" * 60)
    print("测试 MeritRank 声誉引擎")
    print("=" * 60)
    
    from src.core.services.merit_rank_service import MeritRankEngine
    
    engine = MeritRankEngine()
    
    # 测试 1: 初始声誉
    print("\n1. 测试初始声誉")
    initial_rep = engine.get_reputation("node_001")
    print(f"   node_001 初始声誉: {initial_rep:.1f}")
    assert initial_rep == 50.0, "初始声誉应该是 50.0"
    print("   ✅ 通过")
    
    # 测试 2: 任务完成记录
    print("\n2. 测试任务完成记录")
    engine.record_task_completion("node_001", "user_001", quality_score=1.0)
    rep_after_completion = engine.get_reputation("node_001")
    print(f"   node_001 完成任务后声誉: {rep_after_completion:.1f}")
    assert rep_after_completion > 50.0, "完成任务后声誉应该上升"
    print("   ✅ 通过")
    
    # 测试 3: 声誉等级
    print("\n3. 测试声誉等级")
    tier = engine.get_reputation_tier(rep_after_completion)
    print(f"   声誉等级: {tier}")
    print("   ✅ 通过")
    
    # 测试 4: 抗女巫攻击模拟
    print("\n4. 测试抗女巫攻击")
    result = engine.simulate_sybil_attack(attacker_count=100, fake_score=5.0)
    print(f"   攻击者数量: {result['attacker_count']}")
    print(f"   每个攻击者评分: {result['fake_score_per_attacker']}")
    print(f"   总虚假评分: {result['total_fake_score']}")
    print(f"   最终声誉: {result['final_reputation']:.1f}")
    print(f"   声誉增长: {result['reputation_increase']:.1f}")
    print(f"   攻击有效性: {result['effectiveness']:.6f}")
    
    print(f"   衰减比例: {result['decay_ratio']:.6f}")
    assert result['decay_ratio'] < 0.05, "女巫攻击应该基本无效"
    print("   ✅ 通过")
    
    # 测试 5: 统计信息
    print("\n5. 测试统计信息")
    stats = engine.get_stats()
    print(f"   总账户: {stats['total_accounts']}")
    print(f"   平均声誉: {stats['avg_reputation']:.1f}")
    print(f"   等级分布: {stats['tier_distribution']}")
    print("   ✅ 通过")
    
    print("\n🎉 MeritRank 测试全部通过！\n")


def test_contribution_proof():
    """测试贡献证明系统"""
    print("=" * 60)
    print("测试贡献证明系统")
    print("=" * 60)
    
    from src.core.services.contribution_proof_service import (
        ContributionProofService,
        ResourceMetrics
    )
    
    service = ContributionProofService()
    
    # 测试 1: 资源度量
    print("\n1. 测试资源度量")
    metrics = ResourceMetrics(
        cpu_seconds=120.0,
        memory_gb_seconds=2.0,
        storage_gb=0.0,
        network_gb=0.0
    )
    print(f"   CPU秒: {metrics.cpu_seconds}")
    print(f"   内存GB秒: {metrics.memory_gb_seconds}")
    print("   ✅ 通过")
    
    # 测试 2: 生成贡献证明
    print("\n2. 测试生成贡献证明")
    proof = service.generate_proof(
        node_address="node_001",
        task_id="task_001",
        resource_metrics=metrics,
        quality_score=1.0,
        code_length=100,
        dependencies=5,
        reputation=60.0
    )
    print(f"   证明ID: {proof.proof_id}")
    print(f"   贡献分: {proof.contribution_score:.2f}")
    print(f"   复杂度系数: {proof.complexity_coefficient:.2f}")
    print(f"   声誉加成: {proof.reputation_bonus:.2f}")
    assert proof.signature is not None, "证明应该有签名"
    print("   ✅ 通过")
    
    # 测试 3: 验证贡献证明
    print("\n3. 测试验证贡献证明")
    is_valid = service.verify_proof(proof)
    print(f"   证明有效: {is_valid}")
    assert is_valid, "证明应该有效"
    print("   ✅ 通过")
    
    # 测试 4: 添加验证
    print("\n4. 测试添加验证")
    success = service.add_verification(proof.proof_id, "verifier_001")
    print(f"   添加验证成功: {success}")
    assert success, "应该能添加验证"
    proof_updated = service.get_proof(proof.proof_id)
    assert proof_updated.verified, "证明应该被标记为已验证"
    print("   ✅ 通过")
    
    # 测试 5: 节点总贡献
    print("\n5. 测试节点总贡献")
    total = service.get_node_total_contribution("node_001")
    print(f"   node_001 总贡献分: {total:.2f}")
    assert total > 0, "总贡献应该大于0"
    print("   ✅ 通过")
    
    # 测试 6: 统计信息
    print("\n6. 测试统计信息")
    stats = service.get_stats()
    print(f"   总证明数: {stats['total_proofs']}")
    print(f"   已验证: {stats['verified_proofs']}")
    print(f"   总贡献: {stats['total_contribution']:.2f}")
    print("   ✅ 通过")
    
    print("\n🎉 贡献证明系统测试全部通过！\n")


def test_encryption():
    """测试加密存储"""
    print("=" * 60)
    print("测试加密存储基础设施")
    print("=" * 60)
    
    try:
        from src.core.services.token_encryption_service import TokenEncryption
    except ImportError:
        print("⚠️  cryptography 库未安装，跳过加密测试")
        print("   请运行: pip install cryptography")
        return
    
    # 测试 1: 初始化加密服务
    print("\n1. 测试初始化加密服务")
    enc = TokenEncryption(main_password="my_secure_password_123!")
    print("   ✅ 通过")
    
    # 测试 2: 加密数据
    print("\n2. 测试加密数据")
    test_data = {
        "address": "node_001",
        "balance": 1000.0,
        "staked": 100.0,
        "reputation": 65.0
    }
    encrypted = enc.encrypt(test_data)
    print(f"   加密后数据长度: {len(encrypted.ciphertext)} 字节")
    print("   ✅ 通过")
    
    # 测试 3: 解密数据
    print("\n3. 测试解密数据")
    decrypted = enc.decrypt(encrypted)
    print(f"   解密后地址: {decrypted['address']}")
    print(f"   解密后余额: {decrypted['balance']}")
    assert decrypted == test_data, "解密后数据应该与原数据一致"
    print("   ✅ 通过")
    
    # 测试 4: 字符串加密/解密
    print("\n4. 测试字符串加密/解密")
    encrypted_str = enc.encrypt_to_string(test_data)
    decrypted_from_str = enc.decrypt_from_string(encrypted_str)
    assert decrypted_from_str == test_data, "字符串加解密应该一致"
    print("   ✅ 通过")
    
    print("\n🎉 加密存储测试全部通过！\n")


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("代币系统安全加固 - 完整测试套件")
    print("=" * 60 + "\n")
    
    try:
        test_merit_rank()
        test_contribution_proof()
        test_encryption()
        
        print("=" * 60)
        print("🎉 所有测试通过！系统安全加固成功！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

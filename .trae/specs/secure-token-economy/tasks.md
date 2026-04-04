# Tasks

## Phase 0: 声誉系统基础 (P0 - 新增)

- [ ] Task 0.1: 实现 MeritRank 声誉引擎
  - [ ] SubTask 0.1.1: 创建 `MeritRankEngine` 类，实现核心算法
  - [ ] SubTask 0.1.2: 实现传递衰减函数 `transmission_decay(score, distance)`
  - [ ] SubTask 0.1.3: 实现连接衰减函数 `connection_decay(score, connections)`
  - [ ] SubTask 0.1.4: 实现周期衰减函数 `period_decay(score, periods)`
  - [ ] SubTask 0.1.5: 实现综合声誉计算 `calculate_reputation(feedbacks)`
  - [ ] SubTask 0.1.6: 编写 MeritRank 单元测试

- [ ] Task 0.2: 实现贡献证明系统
  - [ ] SubTask 0.2.1: 创建 `ContributionProof` 数据结构
  - [ ] SubTask 0.2.2: 实现贡献证明生成器 `generate_proof(task_result, metrics)`
  - [ ] SubTask 0.2.3: 实现贡献证明验证器 `verify_proof(proof, signature)`
  - [ ] SubTask 0.2.4: 实现贡献分计算公式
  - [ ] SubTask 0.2.5: 编写贡献证明单元测试

- [ ] Task 0.3: 实现 BARM 防篡改机制
  - [ ] SubTask 0.3.1: 创建 `BARMConsensus` 类
  - [ ] SubTask 0.3.2: 实现随机验证伙伴选择算法
  - [ ] SubTask 0.3.3: 实现分布式声誉共识计算
  - [ ] SubTask 0.3.4: 实现影响力限制机制（单节点最大 10%）
  - [ ] SubTask 0.3.5: 编写 BARM 单元测试

## Phase 1: 核心安全机制 (P0)

- [ ] Task 1: 实现加密存储基础设施
  - [ ] SubTask 1.1: 创建 `TokenEncryption` 类，实现 AES-256-GCM 加密/解密
  - [ ] SubTask 1.2: 实现基于 PBKDF2 的密钥派生函数
  - [ ] SubTask 1.3: 实现数据完整性 HMAC 签名和验证
  - [ ] SubTask 1.4: 编写加密模块单元测试

- [ ] Task 2: 实现代币数据持久化存储
  - [ ] SubTask 2.1: 创建 `TokenRepository` 接口定义
  - [ ] SubTask 2.2: 实现 `EncryptedTokenRepository` 加密存储实现
  - [ ] SubTask 2.3: 创建数据库表结构（accounts, transactions, stakes, contributions, reputation_events）
  - [ ] SubTask 2.4: 实现数据迁移工具（从内存迁移到数据库）
  - [ ] SubTask 2.5: 编写仓储层单元测试

- [ ] Task 3: 扩展权限系统
  - [ ] SubTask 3.1: 在 `Permission` 枚举添加代币和声誉相关权限
  - [ ] SubTask 3.2: 更新 `ROLES` 字典添加新权限映射
  - [ ] SubTask 3.3: 创建 `TokenPermissionService` 代币权限服务
  - [ ] SubTask 3.4: 实现权限检查装饰器 `@require_token_permission`
  - [ ] SubTask 3.5: 编写权限扩展单元测试

- [ ] Task 4: 扩展审计日志系统
  - [ ] SubTask 4.1: 在 `AuditAction` 枚举添加代币和声誉操作类型
  - [ ] SubTask 4.2: 创建 `TokenAuditLogger` 代币审计记录器
  - [ ] SubTask 4.3: 实现代币操作审计记录（包含前后余额）
  - [ ] SubTask 4.4: 实现异常操作检测和告警
  - [ ] SubTask 4.5: 编写审计扩展单元测试

## Phase 2: 服务层安全加固 (P1)

- [ ] Task 5: 创建代币安全服务层
  - [ ] SubTask 5.1: 创建 `TokenSecurityService` 类
  - [ ] SubTask 5.2: 实现安全转账方法（权限检查 + 审计 + 加密）
  - [ ] SubTask 5.3: 实现安全质押方法
  - [ ] SubTask 5.4: 实现管理员代币调整方法（二次验证）
  - [ ] SubTask 5.5: 编写安全服务单元测试

- [ ] Task 6: 重构 TokenEconomy 核心类
  - [ ] SubTask 6.1: 修改 `TokenEconomy` 使用加密仓储
  - [ ] SubTask 6.2: 添加权限检查到所有修改操作
  - [ ] SubTask 6.3: 集成审计日志到所有操作
  - [ ] SubTask 6.4: 集成 MeritRank 声誉计算
  - [ ] SubTask 6.5: 保持向后兼容的 API 接口
  - [ ] SubTask 6.6: 编写集成测试

- [ ] Task 7: 实现交易签名机制
  - [ ] SubTask 7.1: 创建 `TransactionSigner` 类
  - [ ] SubTask 7.2: 实现交易签名生成（包含随机数防重放）
  - [ ] SubTask 7.3: 实现交易签名验证
  - [ ] SubTask 7.4: 集成到关键交易流程
  - [ ] SubTask 7.5: 编写签名机制单元测试

## Phase 3: 密钥管理与备份 (P2)

- [ ] Task 8: 实现密钥管理
  - [ ] SubTask 8.1: 创建 `KeyManager` 密钥管理类
  - [ ] SubTask 8.2: 实现主密码输入和密钥派生
  - [ ] SubTask 8.3: 实现密钥轮换机制
  - [ ] SubTask 8.4: 实现恢复密钥生成和验证
  - [ ] SubTask 8.5: 编写密钥管理单元测试

- [ ] Task 9: 实现数据备份与恢复
  - [ ] SubTask 9.1: 创建 `TokenBackupService` 备份服务
  - [ ] SubTask 9.2: 实现加密备份文件生成
  - [ ] SubTask 9.3: 实现备份完整性校验
  - [ ] SubTask 9.4: 实现从备份恢复数据
  - [ ] SubTask 9.5: 编写备份恢复单元测试

## Phase 4: 调度系统集成 (P1)

- [ ] Task 10: 声誉驱动调度
  - [ ] SubTask 10.1: 修改调度算法考虑节点声誉
  - [ ] SubTask 10.2: 实现声誉优先级队列
  - [ ] SubTask 10.3: 实现任务分配的声誉权重
  - [ ] SubTask 10.4: 编写调度集成测试

- [ ] Task 11: 激励机制优化
  - [ ] SubTask 11.1: 实现基于声誉的奖励加成
  - [ ] SubTask 11.2: 实现任务失败的声誉惩罚
  - [ ] SubTask 11.3: 实现周期性声誉衰减
  - [ ] SubTask 11.4: 编写激励机制测试

## Phase 5: 集成与验证

- [ ] Task 12: 更新依赖注入容器
  - [ ] SubTask 12.1: 注册 `TokenEncryption` 到容器
  - [ ] SubTask 12.2: 注册 `EncryptedTokenRepository` 到容器
  - [ ] SubTask 12.3: 注册 `TokenSecurityService` 到容器
  - [ ] SubTask 12.4: 注册 `MeritRankEngine` 到容器
  - [ ] SubTask 12.5: 注册 `ContributionProofService` 到容器
  - [ ] SubTask 12.6: 注册 `BARMConsensus` 到容器
  - [ ] SubTask 12.7: 更新 `TokenEconomyService` 使用新依赖

- [ ] Task 13: 更新配置系统
  - [ ] SubTask 13.1: 添加 `TokenSecuritySettings` 配置类
  - [ ] SubTask 13.2: 添加 `MeritRankSettings` 配置类
  - [ ] SubTask 13.3: 配置加密参数（密钥派生迭代次数等）
  - [ ] SubTask 13.4: 配置声誉衰减参数
  - [ ] SubTask 13.5: 配置备份策略
  - [ ] SubTask 13.6: 配置审计保留策略

- [ ] Task 14: 端到端测试与文档
  - [ ] SubTask 14.1: 编写端到端安全测试
  - [ ] SubTask 14.2: 编写抗女巫攻击测试
  - [ ] SubTask 14.3: 编写安全配置指南
  - [ ] SubTask 14.4: 更新 API 文档
  - [ ] SubTask 14.5: 编写迁移指南

# Task Dependencies

- [Task 0.2] depends on [Task 0.1]
- [Task 0.3] depends on [Task 0.1]
- [Task 2] depends on [Task 1]
- [Task 5] depends on [Task 1, Task 2, Task 3, Task 4]
- [Task 6] depends on [Task 5, Task 0.1, Task 0.2]
- [Task 7] depends on [Task 5]
- [Task 8] depends on [Task 1]
- [Task 9] depends on [Task 2, Task 8]
- [Task 10] depends on [Task 0.1]
- [Task 11] depends on [Task 10]
- [Task 12] depends on [Task 1, Task 2, Task 5, Task 0.1, Task 0.2, Task 0.3]
- [Task 13] depends on [Task 1, Task 8, Task 9, Task 0.1]
- [Task 14] depends on [Task 12, Task 13]

# Parallel Execution

以下任务可以并行执行：
- Task 0.1, Task 0.3, Task 1, Task 3, Task 4 (无依赖)
- Task 0.2, Task 7, Task 8 (在 Task 0.1/Task 5 完成后)
- Task 10, Task 11 (在 Task 0.1 完成后)
- Task 13, Task 14 (在 Task 12 完成后)

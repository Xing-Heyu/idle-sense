# 代码质量与安全修复规范

## Why

项目存在多个高优先级安全问题（API无限流、代币经济集成验证）和中等优先级代码质量问题（异常上下文缺失、测试覆盖不足、会话内存存储、嵌套if优化），以及低优先级代码整洁问题（未使用导入、废弃类型注解、E2E测试不足、安全头缺失）。这些问题影响系统的安全性、可维护性和可扩展性。

## What Changes

### 高优先级修复 (P0)
- **H1**: 验证代币经济服务集成，添加端到端集成测试，更新checklist状态
- **H2**: 为API端点添加请求限流机制，防止DoS攻击

### 中优先级修复 (P1)
- **M1**: 修复20+处异常重新抛出时缺少`from`子句的问题（B904规则）
- **M2**: 为MeritRank、ContributionProof、TokenEncryption服务添加独立单元测试
- **M3**: 重构会话管理支持Redis存储，支持水平扩展
- **M4**: 优化嵌套if语句为单个条件（SIM102规则）

### 低优先级修复 (P2)
- **L1**: 清理约80处未使用的导入语句（F401规则）
- **L2**: 更新废弃的类型注解为内置类型（UP035规则）
- **L3**: 扩展E2E测试覆盖更多场景
- **L4**: 为Streamlit Web界面添加安全头配置

## Impact

- Affected specs: secure-token-economy (H1, M2), optimize-implementation (M1, M4, L1, L2)
- Affected code:
  - `src/di/container.py` - 代币经济集成验证
  - `legacy/scheduler/simple_server.py` - API限流
  - `legacy/` 和 `src/` 目录下多个文件 - 异常处理修复
  - `tests/unit/` - 新增单元测试
  - `src/presentation/streamlit/utils/session_manager.py` - 会话存储重构
  - `src/infrastructure/scheduler/scheduler.py` - 嵌套if优化
  - `tests/e2e/` - E2E测试扩展

## ADDED Requirements

### Requirement: API请求限流

系统应为所有API端点提供请求限流机制，防止DoS攻击。

#### Scenario: 正常请求通过
- **WHEN** 用户在限流范围内发送请求
- **THEN** 请求正常处理

#### Scenario: 超限请求被拒绝
- **WHEN** 用户超过限流阈值发送请求
- **THEN** 返回429 Too Many Requests错误

### Requirement: 异常链完整性

系统应保持异常链完整性，所有异常重新抛出时应包含`from`子句。

#### Scenario: 异常重新抛出保留上下文
- **WHEN** 捕获异常后重新抛出新异常
- **THEN** 新异常应通过`from`子句保留原始异常上下文

### Requirement: 服务单元测试覆盖

系统应为所有核心服务提供独立的单元测试文件。

#### Scenario: MeritRank服务测试
- **WHEN** 运行MeritRank单元测试
- **THEN** 测试覆盖传输衰减、连接衰减、周期衰减、女巫攻击防御

#### Scenario: ContributionProof服务测试
- **WHEN** 运行贡献证明单元测试
- **THEN** 测试覆盖证明生成、签名验证、贡献分计算

#### Scenario: TokenEncryption服务测试
- **WHEN** 运行代币加密单元测试
- **THEN** 测试覆盖AES-256-GCM加密/解密、密钥派生、HMAC签名

### Requirement: 会话持久化存储

系统应支持会话数据的持久化存储，支持水平扩展。

#### Scenario: Redis会话存储
- **WHEN** 配置Redis作为会话存储后端
- **THEN** 会话数据存储在Redis中，支持多实例共享

#### Scenario: 本地缓存回退
- **WHEN** Redis不可用时
- **THEN** 自动回退到本地内存缓存

### Requirement: E2E测试场景覆盖

系统应提供完整的端到端测试场景覆盖。

#### Scenario: 完整用户流程测试
- **WHEN** 运行E2E测试
- **THEN** 覆盖用户注册→登录→提交任务→查看结果完整流程

#### Scenario: 代币经济流程测试
- **WHEN** 运行代币经济E2E测试
- **THEN** 覆盖质押→执行→奖励完整流程

## MODIFIED Requirements

### Requirement: 代币经济服务集成验证

系统应验证MeritRank、ContributionProof、TokenEncryption三个服务完全集成到主调度流程。

#### Scenario: UseCase调用验证
- **WHEN** CompleteTaskWithTokenEconomyUseCase执行
- **THEN** MeritRankEngine和ContributionProofService被正确调用

#### Scenario: 集成测试通过
- **WHEN** 运行代币经济集成测试
- **THEN** 所有服务协同工作正常

## REMOVED Requirements

无移除的需求。

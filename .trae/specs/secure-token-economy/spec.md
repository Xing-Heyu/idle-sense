# 代币系统安全加固规范 v2

## Why

在个人部署场景下，代币系统的账户数据存储在内存中，缺乏加密保护、权限控制和审计追踪，导致代币金额可能被随意更改。结合学术研究成果（MeritRank、BARM、PoC等），本方案采用**声誉驱动 + 贡献证明**的混合架构，从根本上解决激励与安全问题。

## What Changes

### 核心架构转变
- **从代币转向声誉**: 引入 MeritRank 声誉系统，贡献分不直接等于代币
- **贡献证明机制**: 采用 PoC (Proof of Contribution) 替代 PoW/PoS
- **抗女巫攻击**: 通过衰减机制让刷分行为无效
- **防篡改设计**: 基于 BARM 的分布式声誉共识

### 具体实现
- 实现账户数据的加密存储机制
- 添加代币操作的权限控制和访问验证
- 实现交易签名和验证机制
- 添加完整的代币操作审计日志
- 实现数据持久化和完整性校验

### 架构改进
- **BREAKING**: 代币数据存储从内存迁移到加密数据库
- 新增 `TokenSecurityService` 安全服务层
- 新增 `MeritRankEngine` 声誉计算引擎
- 新增 `ContributionProof` 贡献证明系统
- 扩展 `Permission` 枚举添加代币相关权限
- 扩展 `AuditAction` 枚举添加代币操作审计

## Impact

- Affected specs: 代币经济系统、权限系统、审计系统、调度系统
- Affected code:
  - `legacy/token_economy/__init__.py`
  - `src/core/services/token_economy_service.py`
  - `src/core/services/merit_rank_service.py` (新增)
  - `src/core/services/contribution_proof_service.py` (新增)
  - `src/core/security/permission.py`
  - `src/infrastructure/audit/audit_logger.py`
  - `src/infrastructure/repositories/` (新增代币仓储)

---

## 核心设计方案

### 方案一：MeritRank 声誉系统（推荐）

基于论文 *MeritRank: Sybil Tolerant Reputation for Merit-based Tokenomics* 的核心思想：

#### 核心机制

```
声誉计算 = 反馈聚合 × 衰减因子

衰减因子 = 传递衰减 × 连接衰减 × 周期衰减
```

#### 三种衰减机制

| 衰减类型 | 公式 | 作用 |
|---------|------|------|
| 传递衰减 | `score × 0.8^distance` | 防止远距离刷分 |
| 连接衰减 | `score × 1/log(1+connections)` | 防止多账号互刷 |
| 周期衰减 | `score × 0.95^periods` | 防止历史贡献永久有效 |

#### 声誉计算流程

```
┌─────────────────────────────────────────────────────────────┐
│                    MeritRank 计算引擎                        │
├─────────────────────────────────────────────────────────────┤
│  1. 收集反馈数据                                             │
│     - 任务完成质量评分                                       │
│     - 节点在线时长                                           │
│     - 任务响应速度                                           │
│                                                             │
│  2. 应用衰减机制                                             │
│     - 传递衰减：间接信任链衰减                               │
│     - 连接衰减：连接数越多，单连接权重越低                   │
│     - 周期衰减：每周自动衰减 5%                              │
│                                                             │
│  3. 计算综合声誉                                             │
│     reputation = Σ(feedback × decay_factors)                │
│                                                             │
│  4. 声誉等级映射                                             │
│     - Platinum: ≥90 (调度优先级 +3)                         │
│     - Gold: ≥75 (调度优先级 +2)                             │
│     - Silver: ≥60 (调度优先级 +1)                           │
│     - Bronze: ≥40 (调度优先级 +0)                           │
│     - Untrusted: <40 (任务限制)                             │
└─────────────────────────────────────────────────────────────┘
```

#### 抗女巫攻击效果

```python
# 攻击场景：用户创建 100 个账号互相刷分
# MeritRank 防御效果：

攻击者尝试:
  创建 100 个账号 → 连接衰减生效 → 每个连接权重 = 1/log(101) ≈ 0.22
  互相评分 5 分 → 传递衰减生效 → 间接信任几乎为 0
  结果：总声誉 ≈ 100 × 5 × 0.22 × 0.01 ≈ 0.11 分

正常用户:
  1 个账号 → 10 个真实连接 → 连接权重 = 1/log(11) ≈ 0.41
  收到 10 个 5 分评价 → 声誉 = 10 × 5 × 0.41 = 20.5 分
  结果：正常用户声誉远高于攻击者
```

---

### 方案二：贡献证明系统 (PoC)

基于论文 *A proof of contribution in blockchain using game theoretical deep learning model*：

#### 贡献分计算公式

```
贡献分 = 累计算力时长 × 任务复杂度系数 × 质量因子 × 声誉加成

其中：
- 累计算力时长 = Σ(CPU核心数 × 在线时长)
- 任务复杂度系数 = f(代码行数, 依赖数, 计算强度)
- 质量因子 = 任务成功率 × 结果验证通过率
- 声誉加成 = 1 + (reputation - 50) / 100
```

#### 贡献证明流程

```
┌─────────────────────────────────────────────────────────────┐
│                   贡献证明生成流程                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  节点完成任务                                                │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────┐                                            │
│  │ 任务结果    │                                            │
│  │ + 执行日志  │                                            │
│  │ + 资源度量  │                                            │
│  └─────────────┘                                            │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────┐     ┌─────────────┐                       │
│  │ 结果验证    │────▶│ 验证节点    │                       │
│  │ (随机抽样)  │     │ (高声誉)    │                       │
│  └─────────────┘     └─────────────┘                       │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────┐                                            │
│  │ 生成贡献证明 │                                            │
│  │ - 工作量证明 │                                            │
│  │ - 时间戳签名 │                                            │
│  │ - 验证者背书 │                                            │
│  └─────────────┘                                            │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────┐                                            │
│  │ 更新贡献分  │                                            │
│  │ + 记录审计  │                                            │
│  └─────────────┘                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### 方案三：BARM 防篡改机制

基于论文 *BARM: A decentralized and manipulation-resistant reputation management approach*：

#### 核心设计

```python
class BARMReputation:
    """BARM 声誉管理 - 防篡改设计"""
    
    # 1. 防中心化：高声誉节点权力受限
    MAX_INFLUENCE_RATIO = 0.1  # 单节点最大影响力 10%
    
    # 2. 防共谋：伙伴选择随机化
    def select_verification_partner(self, node_id: str) -> str:
        """随机选择验证伙伴，防止固定搭档"""
        candidates = self.get_high_reputation_nodes()
        weights = self.calculate_selection_weights(candidates)
        return random.choices(candidates, weights=weights)[0]
    
    # 3. 分布式共识：声誉由多节点共同计算
    def calculate_reputation(self, node_id: str) -> float:
        """分布式声誉计算"""
        validators = self.select_validators(node_id, count=5)
        scores = []
        for v in validators:
            score = v.evaluate(node_id)
            scores.append(score)
        
        # 取中位数，防止单点操纵
        return statistics.median(scores)
```

---

## 综合实施方案

### 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                        表现层 (Presentation)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Streamlit  │  │     CLI     │  │   REST API  │              │
│  │   Web UI    │  │   Client    │  │   Server    │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        服务层 (Services)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ MeritRank   │  │Contribution │  │   Token     │              │
│  │  Engine     │  │    Proof    │  │  Security   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Permission  │  │   Audit     │  │  BARM       │              │
│  │  Service    │  │  Logger     │  │ Consensus   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    基础设施层 (Infrastructure)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Encrypted  │  │   Audit     │  │  Signature  │              │
│  │  Storage    │  │   Database  │  │  Verifier   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

### 数据流

```
任务完成 → 贡献证明生成 → MeritRank 声誉计算 → BARM 共识验证 → 声誉更新
                │                                    │
                ▼                                    ▼
          审计日志记录                        加密存储更新
```

---

## ADDED Requirements

### Requirement: MeritRank 声誉系统

系统 SHALL 实现 MeritRank 声誉计算引擎，提供抗女巫攻击的声誉评估。

#### Scenario: 声誉计算
- **WHEN** 节点完成任务或收到评价时
- **THEN** 系统应用三种衰减机制计算声誉增量
- **AND** 更新节点的综合声誉分数

#### Scenario: 抗女巫攻击
- **GIVEN** 攻击者创建多个账号互相刷分
- **WHEN** 系统检测到异常连接模式
- **THEN** 连接衰减和传递衰减使刷分效果趋近于零
- **AND** 记录安全告警

### Requirement: 贡献证明系统

系统 SHALL 实现贡献证明机制，记录和验证节点的贡献。

#### Scenario: 贡献证明生成
- **WHEN** 节点完成任务时
- **THEN** 系统生成包含工作量、时间戳、验证签名的贡献证明
- **AND** 贡献证明存储到加密数据库

#### Scenario: 贡献证明验证
- **WHEN** 查询节点贡献时
- **THEN** 系统验证贡献证明的签名和完整性
- **AND** 返回经过验证的贡献分

### Requirement: 加密存储机制

系统 SHALL 对代币账户数据实施加密存储，确保数据在存储层面的安全性。

#### Scenario: 账户数据加密存储
- **WHEN** 创建或更新账户数据时
- **THEN** 敏感字段（余额、质押金额等）使用 AES-256-GCM 加密后存储
- **AND** 加密密钥通过安全的密钥派生函数(PBKDF2)从主密码派生

#### Scenario: 账户数据解密读取
- **WHEN** 读取账户数据时
- **THEN** 系统验证数据完整性 HMAC 签名
- **AND** 解密敏感字段返回明文数据
- **AND** 如果完整性校验失败，拒绝读取并记录安全事件

### Requirement: 权限控制机制

系统 SHALL 对所有代币操作实施基于角色的访问控制。

#### Scenario: 代币操作权限检查
- **WHEN** 用户执行代币相关操作时
- **THEN** 系统检查用户是否拥有对应权限
- **AND** 无权限操作被拒绝并记录审计日志

#### Scenario: 管理员代币管理权限
- **GIVEN** 用户拥有 `TOKEN_MANAGE` 权限
- **WHEN** 用户执行代币调整操作时
- **THEN** 操作需要二次验证（密码或令牌）
- **AND** 所有调整操作记录详细审计日志

### Requirement: 交易签名验证

系统 SHALL 对关键交易实施签名验证机制，防止交易伪造。

#### Scenario: 交易签名生成
- **WHEN** 创建转账、质押等关键交易时
- **THEN** 系统使用用户私钥对交易数据签名
- **AND** 签名包含交易类型、金额、时间戳、随机数

#### Scenario: 交易签名验证
- **WHEN** 处理交易请求时
- **THEN** 系统验证签名有效性
- **AND** 拒绝无效签名的交易
- **AND** 记录签名验证失败的尝试

### Requirement: 审计日志完整性

系统 SHALL 完整记录所有代币操作，支持追溯和异常检测。

#### Scenario: 代币操作审计记录
- **WHEN** 执行任何代币操作时
- **THEN** 记录操作类型、操作者、金额、时间戳、前后余额
- **AND** 审计日志使用追加写入，不可修改
- **AND** 敏感操作（余额调整）需要额外记录原因

#### Scenario: 异常操作检测
- **WHEN** 检测到异常操作模式时
- **THEN** 系统记录安全警告
- **AND** 可配置的自动防护措施（如临时冻结账户）

### Requirement: 数据持久化与备份

系统 SHALL 实现代币数据的持久化存储和定期备份。

#### Scenario: 数据持久化
- **WHEN** 代币数据发生变化时
- **THEN** 数据同步写入加密数据库
- **AND** 写入操作使用事务保证原子性

#### Scenario: 数据备份与恢复
- **GIVEN** 系统配置了备份策略
- **WHEN** 达到备份时间点时
- **THEN** 创建加密备份文件
- **AND** 备份文件包含完整性校验信息
- **AND** 支持从备份恢复数据

### Requirement: 密钥管理

系统 SHALL 提供安全的密钥管理机制。

#### Scenario: 密钥派生
- **WHEN** 系统初始化时
- **THEN** 从主密码派生加密密钥
- **AND** 使用 PBKDF2-HMAC-SHA256 进行密钥派生
- **AND** 迭代次数不少于 100,000 次

#### Scenario: 密钥存储
- **WHEN** 存储派生密钥时
- **THEN** 密钥仅存储在内存中
- **AND** 系统重启后需要重新输入主密码
- **AND** 提供可选的密钥文件存储（加密保护）

## MODIFIED Requirements

### Requirement: 权限枚举扩展

原有权限枚举 SHALL 添加代币相关权限：

```python
class Permission(Enum):
    # ... 现有权限 ...
    
    TOKEN_READ = "token:read"        # 查看代币余额
    TOKEN_TRANSFER = "token:transfer" # 代币转账
    TOKEN_STAKE = "token:stake"       # 质押操作
    TOKEN_MANAGE = "token:manage"     # 代币管理（管理员）
    
    # 新增声誉相关权限
    REPUTATION_READ = "reputation:read"     # 查看声誉
    REPUTATION_VERIFY = "reputation:verify" # 验证声誉（验证节点）
```

### Requirement: 角色权限更新

现有角色定义 SHALL 包含代币和声誉相关权限：

| 角色 | 新增权限 |
|------|---------|
| admin | TOKEN_READ, TOKEN_TRANSFER, TOKEN_STAKE, TOKEN_MANAGE, REPUTATION_READ, REPUTATION_VERIFY |
| user | TOKEN_READ, TOKEN_TRANSFER, TOKEN_STAKE, REPUTATION_READ |
| guest | TOKEN_READ, REPUTATION_READ |
| node_operator | TOKEN_READ, TOKEN_STAKE, REPUTATION_READ, REPUTATION_VERIFY |

### Requirement: 审计操作类型扩展

审计操作枚举 SHALL 添加代币和声誉相关操作：

```python
class AuditAction(Enum):
    # ... 现有操作 ...
    
    TOKEN_DEPOSIT = "token:deposit"
    TOKEN_WITHDRAW = "token:withdraw"
    TOKEN_TRANSFER = "token:transfer"
    TOKEN_STAKE = "token:stake"
    TOKEN_UNSTAKE = "token:unstake"
    TOKEN_REWARD = "token:reward"
    TOKEN_PENALTY = "token:penalty"
    TOKEN_ADJUST = "token:adjust"  # 管理员调整
    
    # 声誉相关
    REPUTATION_UPDATE = "reputation:update"
    REPUTATION_VERIFY = "reputation:verify"
    CONTRIBUTION_PROOF = "contribution:proof"
```

## REMOVED Requirements

### Requirement: 内存存储模式

**Reason**: 内存存储不安全，数据易丢失和篡改
**Migration**: 所有代币数据迁移到加密 SQLite 数据库

---

## 技术选型

### 加密方案
- **对称加密**: AES-256-GCM（提供加密和完整性验证）
- **密钥派生**: PBKDF2-HMAC-SHA256（100,000+ 迭代）
- **签名算法**: HMAC-SHA256（用于数据完整性）

### 声誉系统
- **计算引擎**: MeritRank 算法实现
- **衰减机制**: 传递衰减、连接衰减、周期衰减
- **共识机制**: BARM 分布式共识

### 存储方案
- **主存储**: 加密 SQLite 数据库
- **备份存储**: 加密 JSON 文件
- **缓存**: 内存缓存（加密状态）

### 安全配置
- **密钥轮换**: 支持定期密钥轮换
- **访问控制**: RBAC + 操作级权限
- **审计保留**: 90 天审计日志保留

---

## 风险评估

| 风险 | 等级 | 应对措施 |
|------|------|---------|
| 主密码丢失 | 高 | 提供恢复密钥机制 |
| 性能影响 | 中 | 使用内存缓存减少解密开销 |
| 密钥泄露 | 高 | 密钥不持久化，支持紧急轮换 |
| 备份损坏 | 中 | 多副本备份，完整性校验 |
| 女巫攻击 | 中 | MeritRank 衰减机制 |
| 共谋攻击 | 中 | BARM 随机验证伙伴选择 |

---

## 实施优先级

1. **P0 - 立即实施**: 加密存储、权限控制、审计日志
2. **P1 - 短期实施**: MeritRank 声誉引擎、贡献证明
3. **P2 - 中期实施**: BARM 共识、交易签名、数据持久化
4. **P3 - 长期实施**: 密钥管理、备份恢复

---

## 学术参考

1. **MeritRank**: Nasrulin et al., "MeritRank: Sybil Tolerant Reputation for Merit-based Tokenomics", arXiv 2025
2. **Decentralized Network**: Rodikov G., "Model of an Open, Decentralized Computational Network with Incentive-Based Load Balancing", arXiv 2025
3. **BARM**: "BARM: A decentralized and manipulation-resistant reputation management approach for distributed networks", Springer 2026
4. **PoC**: Wang J., "A proof of contribution in blockchain using game theoretical deep learning model", arXiv 2024
5. **CFN Incentivization**: Liu et al., "A blockchain-based resource sharing incentivization mechanism for multi-to-multi in compute first networking", Computer Networks 2025

---

**最后更新**: 2026-03-29

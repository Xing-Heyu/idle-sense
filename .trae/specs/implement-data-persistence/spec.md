# 数据持久化实现 Spec

## Why

当前 Idle-Sense 项目存在严重的持久化缺陷：

1. **调度器使用纯内存存储** (`OptimizedMemoryStorage`) - 重启后所有任务、节点、结果数据丢失
2. **代币经济无持久化** - 代币余额、交易记录、质押信息重启后丢失
3. **会话管理默认内存后端** - 需要配置 Redis 才能持久化
4. **已有 SQLite 仓储未被使用** - `SQLiteTaskRepository` 和 `SQLiteNodeRepository` 已实现但未集成

根据王勇教授《算力共享与算力市场培育》（2025）论文指出的"三阶段演进机制"，本项目正处于"初始社区→平台搭建"过渡阶段，**数据持久化是平台化的基础前提**。论文强调"制度性建设有待完善"，持久化正是其中的核心基础设施。

## What Changes

### 核心修改

- **调度器集成 SQLite 存储** - 替换 `OptimizedMemoryStorage` 为基于 SQLite 的持久化存储
- **代币经济持久化** - 创建 `SQLiteTokenRepository` 实现代币余额、交易、质押的持久化存储
- **会话管理优化** - 默认启用文件持久化作为 fallback
- **创建 data 目录结构** - 确保数据库文件有标准存储位置

### 新增文件

- `src/infrastructure/repositories/sqlite_token_repository.py` - 代币仓储
- `src/infrastructure/persistence/persistent_storage.py` - 统一持久化管理器

### 修改文件

- `legacy/scheduler/simple_server.py` - 集成 SQLite 存储
- `legacy/token_economy/__init__.py` - 添加持久化支持
- `src/presentation/streamlit/utils/session_manager.py` - 优化会话持久化

## Impact

- Affected specs: secure-token-economy (Task 2 可复用)
- Affected code:
  - `legacy/scheduler/simple_server.py` (核心调度器)
  - `legacy/token_economy/` (代币经济模块)
  - `src/infrastructure/repositories/` (仓储层)
  - `src/presentation/streamlit/utils/session_manager.py` (会话管理)

---

## ADDED Requirements

### Requirement: 调度器数据持久化

系统 SHALL 在调度器重启后保留所有关键业务数据。

#### Scenario: 任务数据持久化
- **WHEN** 调度器提交新任务或更新任务状态
- **THEN** 任务数据 SHALL 被写入 SQLite 数据库
- **AND** 调度器重启后，历史任务数据 SHALL 可恢复

#### Scenario: 节点注册数据持久化
- **WHEN** 节点注册或发送心跳
- **THEN** 节点信息 SHALL 被持久化到 SQLite
- **AND** 调度器重启后，节点列表 SHALL 可恢复

#### Scenario: 任务执行结果持久化
- **WHEN** 任务完成并提交结果
- **THEN** 执行结果 SHALL 被保存到数据库
- **AND** 结果在重启后仍可查询

### Requirement: 代币经济数据持久化

系统 SHALL 提供代币经济数据的完整持久化能力。

#### Scenario: 代币余额持久化
- **WHEN** 用户获得或消费代币
- **THEN** 余额变更 SHALL 被原子性写入数据库
- **AND** 重启后余额 SHALL 保持一致

#### Scenario: 交易记录持久化
- **WHEN** 发生代币转账/奖励/消费交易
- **THEN** 交易记录 SHALL 被完整保存
- **AND** 支持按时间、类型查询历史交易

#### Scenario: 质押信息持久化
- **WHEN** 用户进行质押操作
- **THEN** 质押金额、时间、收益状态 SHALL 被持久化
- **AND** 重启后质押关系 SHALL 保持有效

### Requirement: 统一数据目录

系统 SHALL 使用标准化的数据存储目录结构。

#### Scenario: 自动创建数据目录
- **WHEN** 应用首次启动
- **THEN** 系统 SHALL 自动创建 `data/` 目录
- **AND** 创建子目录 `data/db/` 用于数据库文件
- **AND** 创建子目录 `data/backups/` 用于备份文件

---

## MODIFIED Requirements

### Requirement: 会话管理持久化

原需求：会话管理支持 memory 和 redis 后端

修改为：会话管理默认使用文件持久化后端，Redis 作为可选增强

#### Scenario: 会话自动恢复
- **WHEN** 用户登录后关闭浏览器再重新打开
- **THEN** 如果 Redis 未配置，系统 SHALL 尝试从本地文件恢复会话
- **AND** 文件后端 TTL 过期后自动清理

---

## REMOVED Requirements

无

---

## 技术设计要点

### 数据库 Schema 设计

```sql
-- tasks 表（已有）
CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    code TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT,
    user_id TEXT,
    timeout INTEGER DEFAULT 300,
    cpu_request REAL DEFAULT 1.0,
    memory_request INTEGER DEFAULT 512,
    task_type TEXT DEFAULT 'single_node',
    assigned_node TEXT,
    started_at TEXT,
    completed_at TEXT,
    result TEXT,
    error TEXT,
    resources TEXT
);

-- nodes 表（已有）
CREATE TABLE nodes (
    node_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL DEFAULT 'unknown',
    status TEXT NOT NULL DEFAULT 'offline',
    capacity TEXT,
    tags TEXT,
    owner TEXT DEFAULT 'unknown',
    registered_at TEXT,
    last_heartbeat TEXT,
    is_available INTEGER DEFAULT 0,
    is_idle INTEGER DEFAULT 0
);

-- 新增：token_accounts 表
CREATE TABLE token_accounts (
    user_id TEXT PRIMARY KEY,
    balance REAL NOT NULL DEFAULT 0.0,
    frozen_balance REAL NOT NULL DEFAULT 0.0,
    total_earned REAL NOT NULL DEFAULT 0.0,
    total_spent REAL NOT NULL DEFAULT 0.0,
    updated_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 新增：token_transactions 表
CREATE TABLE token_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_hash TEXT UNIQUE NOT NULL,
    from_user_id TEXT,
    to_user_id TEXT NOT NULL,
    amount REAL NOT NULL,
    tx_type TEXT NOT NULL, -- reward, transfer, stake, unstake, penalty
    description TEXT,
    reference_id TEXT, -- task_id or stake_id
    created_at TEXT NOT NULL,
    INDEX idx_tx_from (from_user_id),
    INDEX idx_tx_to (to_user_id),
    INDEX idx_tx_type (tx_type)
);

-- 新增：token_stakes 表
CREATE TABLE token_stakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    amount REAL NOT NULL,
    staked_at TEXT NOT NULL,
    unlocked_at TEXT,
    status TEXT NOT NULL DEFAULT 'active', -- active, withdrawn, penalized
    apy REAL DEFAULT 0.05,
    earned_interest REAL DEFAULT 0.0,
    INDEX idx_stake_user (user_id),
    INDEX idx_stake_status (status)
);
```

### 向后兼容策略

1. **渐进式迁移** - 启动时检测是否为首次运行，如果是则从内存初始化
2. **双写模式** - 迁移期间同时写入内存和数据库
3. **回退机制** - 数据库连接失败时降级到内存模式并发出警告

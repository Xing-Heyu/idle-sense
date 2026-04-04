# 数据持久化架构文档

**文档版本**: v1.0
**最后更新**: 2026-04-04
**适用项目版本**: v1.0.0+

---

## 目录

1. [架构概述](#一架构概述)
2. [数据库 Schema 说明](#二数据库-schema-说明)
3. [存储后端选择机制](#三存储后端选择机制)
4. [环境变量参考](#四环境变量参考)
5. [迁移指南（从内存到 SQLite）](#五迁移指南从内存到-sqlite)
6. [故障排除](#六故障排除)

---

## 一、架构概述

### 1.1 设计理念

> 根据王勇、傅芳宁、陆树檀（清华大学）《算力共享与算力市场培育》（《财经问题研究》2025年第4期）的研究，算力共享平台需经历"初始社区→平台搭建→统一大市场"三阶段演进。本项目通过实现完整的数据持久化基础设施，为向第二阶段过渡奠定基础。

Idle-Sense 的持久化系统采用 **"SQLite + 内存双写"** 策略，在保证数据可靠性的同时维持高性能读写：

```
┌─────────────────────────────────────────────────────────────┐
│                     持久化层架构                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   应用层 (Use Cases / Services)                              │
│         │                                                   │
│         ▼                                                   │
│   ┌─────────────┐                                           │
│   │ Repository  │  统一数据访问接口                          │
│   │   接口层    │                                           │
│   └──────┬──────┘                                           │
│          │                                                   │
│     ┌────┴────┐                                             │
│     ▼         ▼                                             │
│ ┌────────┐ ┌─────────┐                                     │
│ │ 内存缓存 │ │  SQLite  │  双写策略                         │
│ │(LRU/TTL)│ │ 持久存储 │                                    │
│ └────────┘ └─────────┘                                     │
│      │           │                                          │
│      ▼           ▼                                          │
│   快速读取    崩溃恢复                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心设计原则

| 原则 | 实现方式 |
|------|---------|
| 写穿透（Write-Through） | 每次写入同时更新内存缓存和 SQLite |
| 读优先（Read-Aside） | 优先从内存读取，未命中时回源到 SQLite |
| 原子事务 | 代币经济操作使用 SQLite 事务保证一致性 |
| 自动降级 | SQLite 不可用时自动退化为纯内存模式 |

### 1.3 各组件持久化策略

| 组件 | 主存储 | 缓存层 | 一致性保证 |
|------|-------|--------|-----------|
| 调度器任务 | SQLite (`tasks` 表) | 内存 dict | 写穿透，最终一致 |
| 节点信息 | SQLite (`nodes` 表) | 内存 dict + TTL | 心跳驱动刷新 |
| 代币经济 | SQLite (`token_*` 表) | 无（直接事务） | ACID 事务 |
| 用户数据 | JSON 文件 (`data/users/`) | 内存 dict | 懒加载 + 写回 |
| 会话管理 | 文件 / Redis | 可选 Redis | 配置驱动选择 |

---

## 二、数据库 Schema 说明

### 2.1 数据库文件

默认路径：`data/idle_sense.db`

首次运行时由 `src/infrastructure/repositories/sqlite_base.py` 自动初始化。

### 2.2 核心表结构

#### tasks 表 — 任务数据

```sql
CREATE TABLE IF NOT EXISTS tasks (
    task_id    TEXT PRIMARY KEY,
    code       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',
    user_id    TEXT,
    timeout    INTEGER NOT NULL DEFAULT 300,
    cpu_request REAL NOT NULL DEFAULT 1.0,
    memory_request INTEGER NOT NULL DEFAULT 512,
    task_type  TEXT NOT NULL DEFAULT 'compute',
    assigned_node TEXT,
    result     TEXT,
    error      TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_node ON tasks(assigned_node);
```

#### nodes 表 — 节点信息

```sql
CREATE TABLE IF NOT EXISTS nodes (
    node_id    TEXT PRIMARY KEY,
    platform   TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'offline',
    capacity   TEXT NOT NULL DEFAULT '{}',
    tags       TEXT NOT NULL DEFAULT '{}',
    owner      TEXT NOT NULL,
    last_heartbeat TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);
```

#### token_balances 表 — 代币余额

```sql
CREATE TABLE IF NOT EXISTS token_balances (
    user_id    TEXT PRIMARY KEY,
    balance    REAL NOT NULL DEFAULT 0.0,
    frozen     REAL NOT NULL DEFAULT 0.0,
    updated_at TEXT NOT NULL
);
```

#### token_transactions 表 — 代币流水

```sql
CREATE TABLE IF NOT EXISTS token_transactions (
    tx_id      TEXT PRIMARY KEY,
    from_user  TEXT NOT NULL,
    to_user    TEXT NOT NULL,
    amount     REAL NOT NULL,
    tx_type    TEXT NOT NULL,
    reference  TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tx_from ON token_transactions(from_user);
CREATE INDEX IF NOT EXISTS idx_tx_to ON token_transactions(to_user);
```

#### token_stakes 表 — 质押记录

```sql
CREATE TABLE IF NOT EXISTS token_stakes (
    stake_id   TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    amount     REAL NOT NULL,
    status     TEXT NOT NULL DEFAULT 'active',
    started_at TEXT NOT NULL,
    ended_at   TEXT
);
```

### 2.3 目录结构

```
data/
├── idle_sense.db              # SQLite 主数据库（任务、节点、代币）
├── users/                     # 用户 JSON 数据目录
│   ├── {user_id}.json         # 单个用户配置
│   └── ...
├── sessions/                  # 会话文件（file 后端）
│   └── {session_id}.json
└── logs/                      # 运行日志（可选）
```

---

## 三、存储后端选择机制

### 3.1 会话后端切换

会话管理支持两种后端，通过环境变量控制：

| 后端 | 环境值 | 适用场景 | 依赖 |
|------|--------|---------|------|
| 文件后端 | `IDLESENSE_SESSION_BACKEND=file` | 开发、单机部署 | 无额外依赖 |
| Redis 后端 | `IDLESENSE_SESSION_BACKEND=redis` | 生产、多实例部署 | redis-py |

### 3.2 选择流程

```
启动
 │
 ├─ 读取 IDLESENSE_SESSION_BACKEND
 │     │
 │     ├─ "redis" → 验证 IDLESENSE_REDIS_URL
 │     │                │
 │     │                ├─ 有效 → RedisSessionManager
 │     │                └─ 无效 → 回退到 FileSessionManager + 警告日志
 │     │
 │     └─ 其他/未设置 → FileSessionManager（默认）
 │
 └─ 初始化完成
```

### 3.3 降级策略

当 SQLite 不可用（权限不足、磁盘满等），系统行为如下：

1. 记录 WARNING 级别日志
2. 切换至纯内存模式
3. 定期重试连接 SQLite（每 60 秒）
4. 连接恢复后自动同步内存数据到磁盘

---

## 四、环境变量参考

### 4.1 完整变量列表

| 变量名 | 类型 | 默认值 | 说明 |
|--------|------|-------|------|
| `IDLESENSE_DATA_DIR` | string | `./data` | 数据存储根目录，所有相对路径基于此 |
| `IDLESENSE_DB_PATH` | string | `{DATA_DIR}/idle_sense.db` | SQLite 数据库完整路径 |
| `IDLESENSE_SESSION_BACKEND` | enum | `file` | 会话后端：`file` 或 `redis` |
| `IDLESENSE_REDIS_URL` | string | - | Redis 连接 URL（如 `redis://localhost:6379/0`） |
| `IDLESENSE_CACHE_TTL` | int | `300` | 内存缓存过期时间（秒），0 表示永不过期 |
| `IDLESENSE_DB_TIMEOUT` | float | `5.0` | SQLite 操作超时时间（秒） |
| `IDLESENSE_WAL_MODE` | bool | `true` | 是否启用 WAL 日志模式（提升并发读写性能） |

### 4.2 使用示例

```bash
# 生产环境：使用 Redis 会话 + 自定义数据目录
export IDLESENSE_DATA_DIR=/var/lib/idle-sense
export IDLESENSE_SESSION_BACKEND=redis
export IDLESENSE_REDIS_URL=redis://:password@redis-host:6379/0
export IDLESENSE_CACHE_TTL=600

python -m legacy.scheduler.simple_server
```

```bash
# 开发环境：使用默认配置即可（无需设置任何环境变量）
python -m legacy.scheduler.simple_server
```

---

## 五、迁移指南（从内存到 SQLite）

### 5.1 迁移前状态

v1.0.0 之前的版本使用纯内存存储，重启后所有数据丢失。当前版本已内置自动迁移能力。

### 5.2 迁移步骤

**无需手动操作**。系统在以下场景自动执行迁移：

1. **首次启动**：检测到 `data/` 不存在 → 自动创建并初始化数据库
2. **升级启动**：检测到旧格式数据 → 自动执行 schema migration
3. **降级回滚**：SQLite 不可用时 → 自动退化到纯内存模式

### 5.3 手动触发初始化

如需手动重建数据库：

```python
from src.infrastructure.repositories.sqlite_base import init_database

init_database(db_path="data/idle_sense.db")
print("数据库初始化完成")
```

### 5.4 数据验证

迁移完成后，可通过以下命令验证数据完整性：

```bash
# 检查数据库文件完整性
sqlite3 data/idle_sense.db "PRAGMA integrity_check;"

# 查看各表记录数
sqlite3 data/idle_sense.db "
SELECT 'tasks' AS tbl, COUNT(*) FROM tasks
UNION ALL SELECT 'nodes', COUNT(*) FROM nodes
UNION ALL SELECT 'balances', COUNT(*) FROM token_balances;
"
```

---

## 六、故障排除

### 6.1 常见问题

#### Q: 启动时报 `DatabaseLockedError`

**原因**：多个进程同时写入同一 SQLite 文件。

**解决方案**：
- 确保 WAL 模式已启用（`IDLESENSE_WAL_MODE=true`，默认开启）
- 避免多个调度器实例指向同一数据库
- 检查是否有残留的锁文件 `idle_sense.db-wal` / `idle_sense.db-shm`，可安全删除

#### Q: 启动时报 `PermissionError: data/`

**原因**：当前用户对工作目录没有写权限。

**解决方案**：
```bash
# 方案 A：修改数据目录位置
export IDLESENSE_DATA_DIR=/tmp/idle-sense-data

# 方案 B：修正目录权限
chmod 755 .
mkdir -p data
```

#### Q: Redis 后端连接失败

**原因**：Redis 服务未启动或连接参数错误。

**诊断步骤**：
```bash
# 检查 Redis 是否可达
redis-cli -h localhost -p 6379 ping

# 检查环境变量是否正确
echo $IDLESENSE_REDIS_URL
```

**解决方案**：
- 确认 Redis 服务已启动
- 验证 `IDLESENSE_REDIS_URL` 格式正确
- 若无需 Redis，将 `IDLESENSE_SESSION_BACKEND` 设为 `file`

#### Q: 数据库文件损坏

**原因**：异常断电或进程被强制终止。

**解决方案**：
```bash
# 备份现有数据库
cp data/idle_sense.db data/idle_sense.db.backup

# 尝试 SQLite 内置修复
sqlite3 data/idle_sense.db ".recover" > data/recovered.sql
sqlite3 data/idle_sense_new.db < data/recovered.sql

# 替换原文件
mv data/idle_sense_new.db data/idle_sense.db
```

#### Q: 内存缓存与数据库不一致

**原因**：极端情况下双写过程中发生异常。

**解决方案**：
```python
# 清除内存缓存，强制下次从数据库加载
from src.infrastructure.repositories.sqlite_base import clear_cache
clear_cache()
print("缓存已清除，将从数据库重新加载")
```

### 6.2 日志关键词排查

| 关键词 | 含义 | 建议操作 |
|--------|------|---------|
| `fallback to in-memory` | SQLite 不可用，已降级 | 检查磁盘空间和文件权限 |
| `WAL mode enabled` | 正常启用了 WAL 模式 | 无需处理 |
| `cache hit` / `cache miss` | 缓存命中情况 | miss 过多可调大 `CACHE_TTL` |
| `session backend` | 会话后端初始化 | 确认使用的后端类型 |
| `migration applied` | 数据库 schema 已迁移 | 正常，确认无报错即可 |

---

*本文档随持久化功能同步更新，如有疑问请查阅源码中的 `src/infrastructure/repositories/` 目录。*

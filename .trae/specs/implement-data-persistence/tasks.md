# Tasks

## Phase 1: 基础设施准备 (P0)

- [x] Task 1: 创建数据目录结构和初始化脚本 ✅
  - [x] SubTask 1.1: 创建 `src/infrastructure/persistence/__init__.py` 模块
  - [x] SubTask 1.2: 实现 `ensure_data_dirs()` 函数，自动创建 `data/db/` 和 `data/backups/`
  - [x] SubTask 1.3: 实现数据库路径配置管理（支持环境变量覆盖）
  - [x] SubTask 1.4: 编写目录创建单元测试

## Phase 2: 调度器持久化 (P0 - 核心问题修复)

- [x] Task 2: 创建 PersistentTaskStorage 持久化任务存储 ✅
  - [x] SubTask 2.1: 创建 `src/infrastructure/persistence/persistent_task_storage.py`
  - [x] SubTask 2.2: 继承/包装现有 `SQLiteTaskRepository`，添加内存缓存层
  - [x] SubTask 2.3: 实现批量操作支持（批量保存、批量查询）
  - [x] SubTask 2.4: 实现数据库连接池和重连机制
  - [x] SubTask 2.5: 编写持久化任务存储单元测试

- [x] Task 3: 创建 PersistentNodeStorage 持久化节点存储 ✅
  - [x] SubTask 3.1: 创建 `src/infrastructure/persistence/persistent_node_storage.py`
  - [x] SubTask 3.2: 继承/包装现有 `SQLiteNodeRepository`
  - [x] SubTask 3.3: 实现心跳超时自动更新节点状态为 offline
  - [x] SubTask 3.4: 编写持久化节点存储单元测试

- [x] Task 4: 集成持久化存储到调度器 ✅
  - [x] SubTask 4.1: 修改 `legacy/scheduler/simple_server.py`，添加存储后端选择逻辑
  - [x] SubTask 4.2: 创建 `PersistentSchedulerStorage` 类，统一任务和节点存储接口
  - [x] SubTask 4.3: 实现启动时从数据库恢复数据的逻辑
  - [x] SubTask 4.4: 实现优雅关闭时刷新缓存到数据库
  - [x] SubTask 4.5: 添加环境变量 `STORAGE_BACKEND=sqlite|memory` 支持切换
  - [x] SubTask 4.6: 编写调度器集成测试（验证重启后数据保留）

## Phase 3: 代币经济持久化 (P0)

- [x] Task 5: 创建 SQLiteTokenRepository 代币仓储 ✅
  - [x] SubTask 5.1: 创建 `src/infrastructure/repositories/sqlite_token_repository.py`
  - [x] SubTask 5.2: 实现 token_accounts 表操作（余额查询、更新、冻结）
  - [x] SubTask 5.3: 实现 token_transactions 表操作（交易记录、历史查询）
  - [x] SubTask 5.4: 实现 token_stakes 表操作（质押、解质押、利息计算）
  - [x] SubTask 5.5: 实现原子性转账操作（事务保证）
  - [x] SubTask 5.6: 编写代币仓储完整单元测试

- [x] Task 6: 集成代币持久化到 TokenEconomy ✅
  - [x] SubTask 6.1: 修改 `legacy/token_economy/__init__.py`，添加仓储注入点
  - [x] SubTask 6.2: 实现 `TokenEconomyPersistenceAdapter` 适配器类
  - [x] SubTask 6.3: 在关键操作（奖励、消费、转账、质押）中调用仓储
  - [x] SubTask 6.4: 实现首次启动时的账户初始化逻辑
  - [x] SubTask 6.5: 编写代币经济集成测试

## Phase 4: 会话与配置优化 (P1)

- [x] Task 7: 优化会话管理持久化 ✅
  - [x] SubTask 7.1: 创建 `FileSessionBackend` 文件会话后端实现
  - [x] SubTask 7.2: 修改 `SessionConfig` 默认 backend_type 为 "file"
  - [x] SubTask 7.3: 实现 TTL 过期清理机制
  - [x] SubTask 7.4: 编写文件会话后端单元测试

- [x] Task 8: 更新依赖注入和配置 ✅
  - [x] SubTask 8.1: 更新 `src/di/container.py` 注册新的持久化组件
  - [x] SubTask 8.2: 添加 `PersistenceSettings` 配置类到 config/settings.py
  - [x] SubTask 8.3: 配置默认数据库路径和数据保留策略
  - [x] SubTask 8.4: 编写配置验证测试

## Phase 5: 验证与文档 (P1)

- [x] Task 9: 端到端持久化验证测试 ✅
  - [x] SubTask 9.1: 编写调度器重启数据恢复测试
  - [x] SubTask 9.2: 编写代币经济跨重启一致性测试
  - [x] SubTask 9.3: 编写并发写入安全性测试
  - [x] SubTask 9.4: 编写数据库损坏恢复测试

- [x] Task 10: 更新文档 ✅
  - [x] SubTask 10.1: 更新 README.md 添加持久化状态说明
  - [x] SubTask 10.2: 更新项目介绍文档的"已完成功能"表格
  - [x] SubTask 10.3: 创建 `docs/PERSISTENCE.md` 持久化架构说明文档
  - [x] SubTask 10.4: 添加论文引用到相关代码注释（王勇教授研究）

---

# Task Dependencies

- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 1]
- [Task 4] depends on [Task 2, Task 3]
- [Task 5] depends on [Task 1]
- [Task 6] depends on [Task 5]
- [Task 7] depends on [Task 1]
- [Task 8] depends on [Task 4, Task 6, Task 7]
- [Task 9] depends on [Task 4, Task 6, Task 8]
- [Task 10] depends on [Task 9]

# Parallel Execution

以下任务可以并行执行：
- Task 2, Task 3, Task 5, Task 7 (在 Task 1 完成后)
- Task 8 (在 Task 4, Task 6, Task 7 任一完成后可开始部分工作)
- Task 9, Task 10 (在所有核心任务完成后)

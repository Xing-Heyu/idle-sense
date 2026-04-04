# Tasks

## Phase 1: 高优先级修复 (P0)

- [x] Task 1.1: 验证代币经济服务集成
  - [x] SubTask 1.1.1: 检查 `CompleteTaskWithTokenEconomyUseCase` 是否正确调用 `MeritRankEngine`
  - [x] SubTask 1.1.2: 检查 `CompleteTaskWithTokenEconomyUseCase` 是否正确调用 `ContributionProofService`
  - [x] SubTask 1.1.3: 验证 `TokenEncryption` 服务在数据存储流程中的使用
  - [x] SubTask 1.1.4: 添加端到端代币经济集成测试
  - [x] SubTask 1.1.5: 更新 `secure-token-economy/checklist.md` 状态

- [x] Task 1.2: 添加API请求限流机制
  - [x] SubTask 1.2.1: 添加 `slowapi` 依赖到 `requirements.txt`
  - [x] SubTask 1.2.2: 创建限流配置模块 `src/infrastructure/security/rate_limiter.py`
  - [x] SubTask 1.2.3: 在 `simple_server.py` 中集成限流中间件
  - [x] SubTask 1.2.4: 为关键端点配置限流规则（提交任务: 10/分钟，注册: 5/分钟）
  - [x] SubTask 1.2.5: 添加限流单元测试

## Phase 2: 中优先级修复 (P1)

- [x] Task 2.1: 修复异常重新抛出缺少上下文 (B904)
  - [x] SubTask 2.1.1: 修复 `legacy/connection_pool/__init__.py` 第240行
  - [x] SubTask 2.1.2: 修复 `legacy/distributed_lock/__init__.py` 第204行
  - [x] SubTask 2.1.3: 修复 `legacy/message_queue/__init__.py` 第232行
  - [x] SubTask 2.1.4: 修复 `legacy/sandbox_v2/__init__.py` 第533行
  - [x] SubTask 2.1.5: 修复 `legacy/storage/__init__.py` 第411行
  - [x] SubTask 2.1.6: 修复 `src/infrastructure/repositories/redis_node_repository.py` 第42行
  - [x] SubTask 2.1.7: 修复 `src/infrastructure/utils/api_utils.py` 第199行
  - [x] SubTask 2.1.8: 运行 `ruff check --select B904` 确认所有问题已修复

- [x] Task 2.2: 添加新代币经济服务单元测试
  - [x] SubTask 2.2.1: 创建 `tests/unit/test_merit_rank_service.py`
    - 测试 `transmission_decay` 函数
    - 测试 `connection_decay` 函数
    - 测试 `period_decay` 函数
    - 测试 `calculate_reputation` 函数
    - 测试女巫攻击防御效果
  - [x] SubTask 2.2.2: 创建 `tests/unit/test_contribution_proof_service.py`
    - 测试贡献证明生成
    - 测试签名验证
    - 测试贡献分计算
  - [x] SubTask 2.2.3: 创建 `tests/unit/test_token_encryption_service.py`
    - 测试 AES-256-GCM 加密/解密
    - 测试 PBKDF2 密钥派生
    - 测试 HMAC 签名验证
  - [x] SubTask 2.2.4: 确保所有新测试覆盖率 ≥ 90%

- [x] Task 2.3: 重构会话管理支持Redis存储
  - [x] SubTask 2.3.1: 创建 `SessionBackend` 抽象接口
  - [x] SubTask 2.3.2: 实现 `MemorySessionBackend` 内存存储
  - [x] SubTask 2.3.3: 实现 `RedisSessionBackend` Redis存储
  - [x] SubTask 2.3.4: 重构 `SessionManager` 支持可配置后端
  - [x] SubTask 2.3.5: 添加会话存储配置选项
  - [x] SubTask 2.3.6: 添加会话存储单元测试

- [x] Task 2.4: 优化嵌套if语句 (SIM102)
  - [x] SubTask 2.4.1: 修复 `src/infrastructure/scheduler/scheduler.py` 第72-74行 CPU资源检查
  - [x] SubTask 2.4.2: 修复 `src/infrastructure/scheduler/scheduler.py` 第76-78行 内存资源检查
  - [x] SubTask 2.4.3: 修复 `legacy/sandbox.py` 第78-81行 属性访问检查
  - [x] SubTask 2.4.4: 运行 `ruff check --select SIM102` 确认所有问题已修复

## Phase 3: 低优先级修复 (P2)

- [x] Task 3.1: 清理未使用导入 (F401)
  - [x] SubTask 3.1.1: 运行 `ruff check --fix --select F401 legacy/ src/`
  - [x] SubTask 3.1.2: 手动检查并确认自动修复正确
  - [x] SubTask 3.1.3: 运行测试确保无回归

- [x] Task 3.2: 更新废弃类型注解 (UP035)
  - [x] SubTask 3.2.1: 运行 `ruff check --fix --select UP035 legacy/ src/`
  - [x] SubTask 3.2.2: 手动检查并确认自动修复正确
  - [x] SubTask 3.2.3: 运行测试确保无回归

- [x] Task 3.3: 扩展E2E测试覆盖
  - [x] SubTask 3.3.1: 创建 `tests/e2e/test_user_flow.py` - 完整用户流程测试
  - [x] SubTask 3.3.2: 创建 `tests/e2e/test_token_economy_flow.py` - 代币经济流程测试
  - [x] SubTask 3.3.3: 创建 `tests/e2e/test_multi_node.py` - 多节点协同计算测试
  - [x] SubTask 3.3.4: 创建 `tests/e2e/test_fault_recovery.py` - 故障恢复测试

- [x] Task 3.4: 添加Streamlit安全头
  - [x] SubTask 3.4.1: 创建 `src/presentation/streamlit/config/security.py`
  - [x] SubTask 3.4.2: 配置 Content-Security-Policy 头
  - [x] SubTask 3.4.3: 配置 X-Content-Type-Options 头
  - [x] SubTask 3.4.4: 配置 X-Frame-Options 头

## Phase 4: 验证与文档

- [x] Task 4.1: 运行完整测试套件
  - [x] SubTask 4.1.1: 运行所有单元测试
  - [x] SubTask 4.1.2: 运行所有集成测试
  - [x] SubTask 4.1.3: 运行所有E2E测试
  - [x] SubTask 4.1.4: 确认测试覆盖率 ≥ 80%

- [x] Task 4.2: 代码质量检查
  - [x] SubTask 4.2.1: 运行 `ruff check` 确认无错误
  - [x] SubTask 4.2.2: 运行 `mypy` 类型检查
  - [x] SubTask 4.2.3: 确认所有修复符合规范

# Task Dependencies

- [Task 1.2] depends on [Task 1.1] (先验证集成再添加限流测试)
- [Task 2.2] depends on [Task 1.1] (单元测试依赖集成验证完成)
- [Task 2.3] depends on [Task 1.2] (会话存储可能需要限流保护)
- [Task 4.1] depends on [Task 1.1, Task 1.2, Task 2.1, Task 2.2, Task 2.3, Task 2.4, Task 3.1, Task 3.2, Task 3.3, Task 3.4]
- [Task 4.2] depends on [Task 4.1]

# Parallel Execution

以下任务可以并行执行：
- Task 1.1, Task 1.2 (无依赖)
- Task 2.1, Task 2.2, Task 2.4, Task 3.1, Task 3.2 (无依赖)
- Task 2.3, Task 3.3, Task 3.4 (在相关任务完成后)
- Task 4.1, Task 4.2 (顺序执行)

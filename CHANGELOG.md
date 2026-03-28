# 更新日志

本项目版本号遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/) 规范。

## [Unreleased]

### 计划中

- 完善测试覆盖率（目标 >80%）
- 吸引首批外部贡献者
- 推进第一个社区PR合并
- 发布 v1.0.0 正式版

---

## [1.0.0] - 2026-03-28

### 已添加

#### 核心功能
- 项目初始化，搭建完整三层架构
- idle-sense 跨平台闲置检测库框架（支持 Windows/macOS/Linux）
- FastAPI 调度中心基础框架
- 节点客户端基础框架
- Streamlit 网页任务管理界面
- 完整项目文档集

#### 命令行工具
- CLI `scheduler status` 命令 - 检查调度器运行状态
- CLI `node list` 命令 - 列出所有注册节点
- CLI `task submit` 命令 - 提交任务
- CLI `task status` 命令 - 查询任务状态
- CLI `task list` 命令 - 列出所有任务

#### 安全沙箱
- BasicSandbox 完整实现 - 进程级隔离
- DockerSandbox 完整实现 - 容器隔离
- GVisorSandbox 完整实现 - 系统调用过滤（仅Linux）
- FirecrackerSandbox 完整实现 - 微虚拟机生命周期管理
- WASMSandbox 完整实现 - 支持 wasmer/wasmtime 运行时

#### P2P 网络
- Kademlia DHT 节点发现
- Gossip 协议消息传播
- NAT 穿透支持 (STUN/UPnP)
- `_handle_find_value_response` 方法实现

#### 代币经济
- EIP-1559 风格定价引擎
- EigenTrust 声誉系统
- Proof-of-Stake 质押机制
- 在线奖励、任务定价系统

#### 分布式任务
- DAG 引擎 - 有向无环图任务调度
- 数据本地性优化
- 容错机制和重试策略

#### 新架构 (Clean Architecture)
- **表现层 (Presentation Layer)**
  - `src/presentation/streamlit/app.py` - 新版Web界面主入口
  - `src/presentation/streamlit/views/` - 模块化页面组件
    - `auth_page.py` - 认证页面（登录/注册）
    - `task_submission_page.py` - 任务提交页面
    - `task_monitor_page.py` - 任务监控页面
    - `node_management_page.py` - 节点管理页面
    - `system_stats_page.py` - 系统统计页面
    - `task_results_page.py` - 任务结果页面
  - `src/presentation/streamlit/components/sidebar.py` - 侧边栏组件
  - `src/presentation/streamlit/utils/session_manager.py` - 会话管理工具

- **用例层 (Use Cases Layer)**
  - `src/core/use_cases/auth/register_use_case.py` - 用户注册用例
  - `src/core/use_cases/auth/login_use_case.py` - 用户登录用例
  - `src/core/use_cases/auth/logout_use_case.py` - 用户登出用例
  - `src/core/use_cases/system/create_folders_use_case.py` - 文件夹创建用例
  - `src/core/use_cases/system/get_system_stats_use_case.py` - 系统统计用例
  - `src/core/use_cases/node/activate_node_use_case.py` - 节点激活用例
  - `src/core/use_cases/node/get_node_status_use_case.py` - 节点状态用例
  - `src/core/use_cases/node/stop_node_use_case.py` - 节点停止用例
  - `src/core/use_cases/task/submit_task_use_case.py` - 任务提交用例
  - `src/core/use_cases/task/cancel_task_use_case.py` - 任务取消用例
  - `src/core/use_cases/task/delete_task_use_case.py` - 任务删除用例
  - `src/core/use_cases/task/get_task_status_use_case.py` - 任务状态用例
  - `src/core/use_cases/task/monitor_task_use_case.py` - 任务监控用例

- **服务层 (Services Layer)**
  - `src/core/services/permission_service.py` - 权限检查服务
  - `src/core/services/idle_detection_service.py` - 闲置检测服务
  - `src/core/services/token_economy_service.py` - 代币经济服务

- **基础设施层 (Infrastructure Layer)**
  - `src/infrastructure/external/scheduler_client.py` - 调度器客户端
  - `src/infrastructure/repositories/user_repository.py` - 用户仓储实现
  - `src/infrastructure/repositories/node_repository.py` - 节点仓储实现
  - `src/infrastructure/repositories/task_repository.py` - 任务仓储实现

- **依赖注入 (Dependency Injection)**
  - `src/di/container.py` - 统一依赖注入容器

#### 单元测试
- 新增 593 个单元测试
- `tests/unit/test_folder_use_case.py` - 文件夹用例测试
- `tests/unit/test_permission_service.py` - 权限服务测试
- `tests/unit/test_session_manager.py` - 会话管理测试
- `tests/unit/test_use_cases.py` - 认证用例测试
- `tests/unit/test_idle_sense.py` - 闲置检测测试
- `tests/unit/test_scheduler.py` - 调度器测试
- `tests/unit/test_sandbox.py` - 沙箱测试
- `tests/unit/test_p2p_network.py` - P2P网络测试
- `tests/unit/test_token_economy.py` - 代币经济测试

### 变更

#### 架构重构
- **web_interface.py 重构**
  - 将 1986 行的"上帝类"拆分为多个职责单一的模块
  - 用户管理迁移至 `RegisterUseCase` 和 `LoginUseCase`
  - 权限管理迁移至 `PermissionService`
  - 文件夹管理迁移至 `CreateFoldersUseCase` 和 `FolderService`
  - API调用统一使用 `SchedulerClient`
  - UI页面拆分为独立的页面组件

- **代码质量改进**
  - 使用 Python 3.9+ 类型注解 (`dict` 替代 `Dict`, `tuple` 替代 `Tuple`)
  - 移除未使用的导入
  - 统一代码风格

- 项目初始版本已设为 1.0.0（在 idle_sense/__init__.py 中定义）
- 修复测试文件导入路径 (distributed_task_v2, sandbox_v2, websocket_comm)
- 更新 README.md 文档，添加 CLI 使用说明和沙箱平台支持表
- 完成 web_interface.py 重构，拆分为多个职责单一的模块
- 统一配置管理到 config/settings.py
- 实现依赖注入容器 src/di/container.py

### 依赖
- 新增 wasmtime 作为 WASM 沙箱运行时 (跨平台支持)
- Docker Desktop 作为可选依赖 (容器沙箱)
- Redis 作为可选依赖 (分布式存储)
- 新增 593 个单元测试，通过率 99.7%

### 文档
- 更新 README.md - 项目主文档
- 更新 CHANGELOG.md - 版本变更记录
- 更新 USER_GUIDE.md - 用户使用指南
- 更新 CONTRIBUTING.md - 贡献指南
- 更新 MANIFESTO.md - 项目宣言
- 更新 docs/API_REFERENCE.md - API参考文档
- 更新 docs/ARCHITECTURE.md - 架构文档
- 更新 docs/QUICKSTART.md - 快速入门指南
- 更新 docs/DEPLOYMENT.md - 部署指南
- 更新 docs/DESIGN_DECISIONS.md - 设计决策文档
- 更新 docs/FEDERATION.md - 联邦协议文档

---

## 版本历史说明

### 版本号格式
- **主版本号**: 不兼容的API变更
- **次版本号**: 向后兼容的功能新增
- **修订号**: 向后兼容的问题修复

### 变更类型
- `已添加`: 新功能
- `已变更`: 现有功能的变更
- `已弃用`: 即将移除的功能
- `已移除`: 已移除的功能
- `已修复`: Bug修复
- `安全`: 安全相关的修复

---

**最后更新**: 2026-03-28

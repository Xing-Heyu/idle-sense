# 未使用代码扫描报告

**生成日期**: 2026-03-28  
**扫描范围**: src/, legacy/, config/ 目录下的所有 Python 源代码文件  
**使用工具**: ruff (F401, F841), vulture (静态分析)

---

## 一、报告摘要

| 类型 | 数量 | 说明 |
|------|------|------|
| 未使用的导入语句 | 71 | 已导入但未被使用的模块或对象 |
| 未使用的局部变量 | 4 | 已赋值但从未被读取的变量 |
| 未使用的函数/方法 | 200+ | 已定义但从未被调用的函数或方法 |
| 未使用的类 | 15+ | 已定义但从未被实例化的类 |
| 未使用的变量/常量 | 100+ | 已定义但从未被引用的变量或常量 |
| 注释掉的代码块 | 0 | 未发现明显的注释代码块 |

---

## 二、未使用的导入语句 (F401)

### 2.1 核心源代码 (src/)

| 文件路径 | 行号 | 未使用的导入 | 说明 |
|----------|------|--------------|------|
| [launch_gui.py](file:///c:/idle-sense/launch_gui.py#L6) | 6 | `os` | 导入但未使用 |
| [src/core/security/permission.py](file:///c:/idle-sense/src/core/security/permission.py#L10) | 10 | `typing.Optional` | 导入但未使用 |
| [src/core/use_cases/auth/login_use_case.py](file:///c:/idle-sense/src/core/use_cases/auth/login_use_case.py#L17) | 17 | `typing.Optional` | 导入但未使用 |
| [src/core/use_cases/auth/login_use_case.py](file:///c:/idle-sense/src/core/use_cases/auth/login_use_case.py#L19) | 19 | `src.core.entities.User` | 导入但未使用 |
| [src/core/use_cases/auth/register_use_case.py](file:///c:/idle-sense/src/core/use_cases/auth/register_use_case.py#L23-L26) | 23-26 | 多个异常类 | `RegistrationPermissionError`, `StorageError`, `UserDataConflictError`, `UsernameValidationError` |
| [src/infrastructure/sandbox/sandbox.py](file:///c:/idle-sense/src/infrastructure/sandbox/sandbox.py#L583) | 583 | `wasmer` | 可选依赖检测导入 |
| [src/infrastructure/sandbox/sandbox.py](file:///c:/idle-sense/src/infrastructure/sandbox/sandbox.py#L589) | 589 | `wasmtime` | 可选依赖检测导入 |
| [src/infrastructure/sandbox/sandbox.py](file:///c:/idle-sense/src/infrastructure/sandbox/sandbox.py#L607) | 607 | `pyodide` | 可选依赖检测导入 |
| [src/infrastructure/sandbox/sandbox.py](file:///c:/idle-sense/src/infrastructure/sandbox/sandbox.py#L613) | 613 | `rustpython` | 可选依赖检测导入 |
| [src/infrastructure/sandbox/sandbox.py](file:///c:/idle-sense/src/infrastructure/sandbox/sandbox.py#L692) | 692 | `wasmer.Memory` | 可选依赖检测导入 |
| [src/infrastructure/security/validators.py](file:///c:/idle-sense/src/infrastructure/security/validators.py#L10) | 10 | `typing.Callable` | 导入但未使用 |
| [src/infrastructure/utils/cache.py](file:///c:/idle-sense/src/infrastructure/utils/cache.py#L11) | 11 | `dataclasses.field` | 导入但未使用 |
| [src/presentation/streamlit/app.py](file:///c:/idle-sense/src/presentation/streamlit/app.py#L16) | 16 | `src.di.container` | 导入但未使用 |
| [src/presentation/streamlit/components/sidebar.py](file:///c:/idle-sense/src/presentation/streamlit/components/sidebar.py#L13) | 13 | `typing.Optional` | 导入但未使用 |
| [src/presentation/streamlit/views/system_stats_page.py](file:///c:/idle-sense/src/presentation/streamlit/views/system_stats_page.py#L12) | 12 | `plotly.graph_objects` (as `go`) | 导入但未使用 |

### 2.2 Legacy 代码 (legacy/)

| 文件路径 | 行号 | 未使用的导入 | 说明 |
|----------|------|--------------|------|
| [legacy/distributed_task_v2/dag_engine.py](file:///c:/idle-sense/legacy/distributed_task_v2/dag_engine.py#L17-L18) | 17-18 | `hashlib`, `json` | 导入但未使用 |
| [legacy/distributed_task_v2/data_locality.py](file:///c:/idle-sense/legacy/distributed_task_v2/data_locality.py#L15-L16) | 15-16 | `hashlib`, `math` | 导入但未使用 |
| [legacy/distributed_task_v2/fault_tolerance.py](file:///c:/idle-sense/legacy/distributed_task_v2/fault_tolerance.py#L18) | 18 | `json` | 导入但未使用 |
| [legacy/p2p_network/bandwidth.py](file:///c:/idle-sense/legacy/p2p_network/bandwidth.py#L14) | 14 | `asyncio` | 导入但未使用 |
| [legacy/p2p_network/bandwidth.py](file:///c:/idle-sense/legacy/p2p_network/bandwidth.py#L16) | 16 | `collections.defaultdict` | 导入但未使用 |
| [legacy/p2p_network/ipv6_support.py](file:///c:/idle-sense/legacy/p2p_network/ipv6_support.py#L19) | 19 | `typing.Union` | 导入但未使用 |
| [legacy/p2p_network/reputation.py](file:///c:/idle-sense/legacy/p2p_network/reputation.py#L15-L17) | 15-17 | `asyncio`, `hashlib`, `math` | 导入但未使用 |
| [legacy/p2p_network/security.py](file:///c:/idle-sense/legacy/p2p_network/security.py#L17-L19) | 17-19 | `hmac`, `os`, `cryptography.hazmat.primitives.hashes` | 导入但未使用 |
| [legacy/p2p_network/stun.py](file:///c:/idle-sense/legacy/p2p_network/stun.py#L13-L17) | 13,17 | `hashlib`, `time` | 导入但未使用 |
| [legacy/p2p_network/turn.py](file:///c:/idle-sense/legacy/p2p_network/turn.py#L8-L9,L14) | 8-9,14 | `asyncio`, `hashlib`, `collections.OrderedDict` | 导入但未使用 |

### 2.3 测试代码 (tests/)

| 文件路径 | 行号 | 未使用的导入 | 说明 |
|----------|------|--------------|------|
| tests/e2e/test_system.py | 118, 225 | 可选导入 | 测试相关可选导入 |
| tests/integration/test_e2e_distributed.py | 13-37 | 多个导入 | 测试相关导入 |
| tests/integration/test_integration.py | 10, 13, 36, 163 | 多个导入 | 测试相关导入 |
| tests/integration/test_nat_traversal.py | 14 | `AsyncMock` | 导入但未使用 |
| tests/unit/test_bandwidth.py | 5 | `pytest` | 导入但未使用 |
| tests/unit/test_dag_engine.py | 6 | `asyncio` | 导入但未使用 |
| tests/unit/test_data_locality.py | 5, 11 | `pytest`, `LocalityScore` | 导入但未使用 |
| tests/unit/test_p2p_security.py | 6 | `asyncio` | 导入但未使用 |
| tests/unit/test_progress_ws.py | 5-6 | `pytest`, `asyncio` | 导入但未使用 |
| tests/unit/test_registration.py | 8 | `MagicMock`, `patch` | 导入但未使用 |
| tests/unit/test_reputation.py | 5, 11 | `pytest`, `ReputationConfig` | 导入但未使用 |
| tests/unit/test_security_improvements.py | 8, 17 | `patch`, `init_user_management` | 导入但未使用 |
| tests/unit/test_shuffle.py | 5 | `pytest` | 导入但未使用 |
| tests/unit/test_stun.py | 5-6 | `pytest`, `asyncio` | 导入但未使用 |

---

## 三、未使用的局部变量 (F841)

| 文件路径 | 行号 | 变量名 | 说明 |
|----------|------|--------|------|
| [legacy/distributed_task_v2/dag_engine.py](file:///c:/idle-sense/legacy/distributed_task_v2/dag_engine.py#L336) | 336 | `e` | 异常处理中捕获但未使用 |
| [legacy/p2p_network/ipv6_support.py](file:///c:/idle-sense/legacy/p2p_network/ipv6_support.py#L158) | 158 | `addr` | 赋值但未使用 |
| [src/infrastructure/sandbox/sandbox.py](file:///c:/idle-sense/src/infrastructure/sandbox/sandbox.py#L513) | 513 | `result` | 赋值但未使用 |
| [src/presentation/streamlit/views/task_monitor_page.py](file:///c:/idle-sense/src/presentation/streamlit/views/task_monitor_page.py#L202) | 202 | `completed` | 赋值但未使用 |

---

## 四、未使用的函数/方法 (按模块分类)

### 4.1 src/api/ 模块

| 文件路径 | 行号 | 函数/方法名 | 置信度 |
|----------|------|-------------|--------|
| [src/api/node.py](file:///c:/idle-sense/src/api/node.py#L29) | 29 | `activate` | 60% |
| [src/api/user.py](file:///c:/idle-sense/src/api/user.py#L38) | 38 | `login` | 60% |
| [src/api/user.py](file:///c:/idle-sense/src/api/user.py#L43) | 43 | `logout` | 60% |
| [src/api/user.py](file:///c:/idle-sense/src/api/user.py#L48) | 48 | `get_user` | 60% |

### 4.2 src/core/entities/ 模块

| 文件路径 | 行号 | 函数/方法名 | 置信度 |
|----------|------|-------------|--------|
| [src/core/entities/folder.py](file:///c:/idle-sense/src/core/entities/folder.py#L115) | 115 | `get_size` | 60% |
| [src/core/entities/folder.py](file:///c:/idle-sense/src/core/entities/folder.py#L137) | 137 | `get_file_count` | 60% |
| [src/core/entities/node.py](file:///c:/idle-sense/src/core/entities/node.py#L69) | 69 | `is_available_for_task` (property) | 60% |
| [src/core/entities/node.py](file:///c:/idle-sense/src/core/entities/node.py#L84) | 84 | `set_busy` | 60% |
| [src/core/entities/node.py](file:///c:/idle-sense/src/core/entities/node.py#L89) | 89 | `set_idle` | 60% |
| [src/core/entities/node.py](file:///c:/idle-sense/src/core/entities/node.py#L100) | 100 | `get_available_resources` | 60% |
| [src/core/entities/task.py](file:///c:/idle-sense/src/core/entities/task.py#L92) | 92 | `is_finished` (property) | 60% |
| [src/core/entities/user.py](file:///c:/idle-sense/src/core/entities/user.py#L46) | 46 | `is_authenticated` (property) | 60% |

### 4.3 src/core/interfaces/ 模块

| 文件路径 | 行号 | 函数/方法名 | 置信度 |
|----------|------|-------------|--------|
| [src/core/interfaces/providers/cache_provider.py](file:///c:/idle-sense/src/core/interfaces/providers/cache_provider.py#L65) | 65 | `cleanup_expired` | 60% |
| [src/core/interfaces/providers/config_provider.py](file:///c:/idle-sense/src/core/interfaces/providers/config_provider.py#L35) | 35 | `get_required` | 60% |
| [src/core/interfaces/providers/config_provider.py](file:///c:/idle-sense/src/core/interfaces/providers/config_provider.py#L51) | 51 | `reload` | 60% |
| [src/core/interfaces/providers/config_provider.py](file:///c:/idle-sense/src/core/interfaces/providers/config_provider.py#L56) | 56 | `get_scheduler_url` | 60% |
| [src/core/interfaces/providers/config_provider.py](file:///c:/idle-sense/src/core/interfaces/providers/config_provider.py#L61) | 61 | `get_api_timeout` | 60% |
| [src/core/interfaces/providers/config_provider.py](file:///c:/idle-sense/src/core/interfaces/providers/config_provider.py#L66) | 66 | `get_refresh_interval` | 60% |
| [src/core/interfaces/repositories/node_repository.py](file:///c:/idle-sense/src/core/interfaces/repositories/node_repository.py#L100) | 100 | `list_online` | 60% |
| [src/core/interfaces/repositories/node_repository.py](file:///c:/idle-sense/src/core/interfaces/repositories/node_repository.py#L110) | 110 | `list_idle` | 60% |
| [src/core/interfaces/services/task_service.py](file:///c:/idle-sense/src/core/interfaces/services/task_service.py#L122) | 122 | `get_distributed_task_status` | 60% |
| [src/core/interfaces/services/task_service.py](file:///c:/idle-sense/src/core/interfaces/services/task_service.py#L135) | 135 | `get_distributed_task_result` | 60% |

### 4.4 src/core/security/ 模块

| 文件路径 | 行号 | 函数/方法名 | 置信度 |
|----------|------|-------------|--------|
| [src/core/security/permission.py](file:///c:/idle-sense/src/core/security/permission.py#L41) | 41 | `has_permission` | 60% |
| [src/core/security/permission.py](file:///c:/idle-sense/src/core/security/permission.py#L118) | 118 | `assign_role` | 60% |
| [src/core/security/permission.py](file:///c:/idle-sense/src/core/security/permission.py#L129) | 129 | `remove_role` | 60% |
| [src/core/security/permission.py](file:///c:/idle-sense/src/core/security/permission.py#L147) | 147 | `get_user_permissions` | 60% |
| [src/core/security/permission.py](file:///c:/idle-sense/src/core/security/permission.py#L159) | 159 | `get_user_roles` | 60% |
| [src/core/security/permission.py](file:///c:/idle-sense/src/core/security/permission.py#L163) | 163 | `has_role` | 60% |

### 4.5 src/core/services/ 模块

| 文件路径 | 行号 | 函数/方法名 | 置信度 |
|----------|------|-------------|--------|
| [src/core/services/idle_detection_service.py](file:///c:/idle-sense/src/core/services/idle_detection_service.py#L88) | 88 | `get_platform_name` | 60% |
| [src/core/services/idle_detection_service.py](file:///c:/idle-sense/src/core/services/idle_detection_service.py#L97) | 97 | `get_idle_time_seconds` | 60% |
| [src/core/services/idle_detection_service.py](file:///c:/idle-sense/src/core/services/idle_detection_service.py#L107) | 107 | `get_resource_usage` | 60% |
| [src/core/services/idle_detection_service.py](file:///c:/idle-sense/src/core/services/idle_detection_service.py#L121) | 121 | `should_start_task` | 60% |
| [src/core/services/permission_service.py](file:///c:/idle-sense/src/core/services/permission_service.py#L24) | 24 | `check_admin_permission` | 60% |
| [src/core/services/permission_service.py](file:///c:/idle-sense/src/core/services/permission_service.py#L55) | 55 | `ensure_directory_with_permission` | 60% |
| [src/core/services/token_economy_service.py](file:///c:/idle-sense/src/core/services/token_economy_service.py#L40) | 40 | `economy` (property) | 60% |
| [src/core/services/token_economy_service.py](file:///c:/idle-sense/src/core/services/token_economy_service.py#L73) | 73 | `get_account_info` | 60% |
| [src/core/services/token_economy_service.py](file:///c:/idle-sense/src/core/services/token_economy_service.py#L132) | 132 | `stake_tokens` | 60% |
| [src/core/services/token_economy_service.py](file:///c:/idle-sense/src/core/services/token_economy_service.py#L155) | 155 | `unstake_tokens` | 60% |

### 4.6 src/di/ 模块

| 文件路径 | 行号 | 函数/方法名/变量 | 置信度 |
|----------|------|------------------|--------|
| [src/di/container.py](file:///c:/idle-sense/src/di/container.py#L32) | 32 | `Provide` (import) | 90% |
| [src/di/container.py](file:///c:/idle-sense/src/di/container.py#L39) | 39 | `Provide` (variable) | 60% |
| [src/di/container.py](file:///c:/idle-sense/src/di/container.py#L133) | 133 | `idle_detection_service` | 60% |
| [src/di/container.py](file:///c:/idle-sense/src/di/container.py#L140) | 140 | `simple_scheduler` | 60% |
| [src/di/container.py](file:///c:/idle-sense/src/di/container.py#L144) | 144 | `advanced_scheduler` | 60% |
| [src/di/container.py](file:///c:/idle-sense/src/di/container.py#L149) | 149 | `sandbox_factory` | 60% |
| [src/di/container.py](file:///c:/idle-sense/src/di/container.py#L153) | 153 | `sandbox_config` | 60% |
| [src/di/container.py](file:///c:/idle-sense/src/di/container.py#L194) | 194 | `permission_service` | 60% |
| [src/di/container.py](file:///c:/idle-sense/src/di/container.py#L198) | 198 | `create_folders_use_case` | 60% |

### 4.7 src/infrastructure/adapters/ 模块

| 文件路径 | 行号 | 函数/方法名 | 置信度 |
|----------|------|-------------|--------|
| [src/infrastructure/adapters/legacy_adapter.py](file:///c:/idle-sense/src/infrastructure/adapters/legacy_adapter.py#L107) | 107 | `login` | 60% |
| [src/infrastructure/adapters/legacy_adapter.py](file:///c:/idle-sense/src/infrastructure/adapters/legacy_adapter.py#L227) | 227 | `logout` | 60% |
| [src/infrastructure/adapters/legacy_adapter.py](file:///c:/idle-sense/src/infrastructure/adapters/legacy_adapter.py#L404) | 404 | `get_adapter` | 60% |

### 4.8 src/infrastructure/audit/ 模块

| 文件路径 | 行号 | 变量名 | 置信度 |
|----------|------|--------|--------|
| [src/infrastructure/audit/audit_logger.py](file:///c:/idle-sense/src/infrastructure/audit/audit_logger.py#L20) | 20 | `USER_LOGIN` | 60% |
| [src/infrastructure/audit/audit_logger.py](file:///c:/idle-sense/src/infrastructure/audit/audit_logger.py#L21) | 21 | `USER_LOGOUT` | 60% |
| [src/infrastructure/audit/audit_logger.py](file:///c:/idle-sense/src/infrastructure/audit/audit_logger.py#L24) | 24 | `TASK_SUBMIT` | 60% |
| [src/infrastructure/audit/audit_logger.py](file:///c:/idle-sense/src/infrastructure/audit/audit_logger.py#L25) | 25 | `TASK_CANCEL` | 60% |
| [src/infrastructure/audit/audit_logger.py](file:///c:/idle-sense/src/infrastructure/audit/audit_logger.py#L28) | 28 | `NODE_ACTIVATE` | 60% |
| [src/infrastructure/audit/audit_logger.py](file:///c:/idle-sense/src/infrastructure/audit/audit_logger.py#L29) | 29 | `NODE_STOP` | 60% |
| [src/infrastructure/audit/audit_logger.py](file:///c:/idle-sense/src/infrastructure/audit/audit_logger.py#L31) | 31 | `SYSTEM_CONFIG_CHANGE` | 60% |

### 4.9 src/infrastructure/external/ 模块

| 文件路径 | 行号 | 函数/方法名/变量 | 置信度 |
|----------|------|------------------|--------|
| [src/infrastructure/external/scheduler_client.py](file:///c:/idle-sense/src/infrastructure/external/scheduler_client.py#L161) | 161 | `root_data` | 60% |
| [src/infrastructure/external/scheduler_client.py](file:///c:/idle-sense/src/infrastructure/external/scheduler_client.py#L399) | 399 | `exc_tb`, `exc_val` | 100% |
| [src/infrastructure/external/scheduler_client.py](file:///c:/idle-sense/src/infrastructure/external/scheduler_client.py#L504) | 504 | `get_result` | 60% |

### 4.10 src/infrastructure/repositories/ 模块

| 文件路径 | 行号 | 函数/方法名 | 置信度 |
|----------|------|-------------|--------|
| [src/infrastructure/repositories/node_repository.py](file:///c:/idle-sense/src/infrastructure/repositories/node_repository.py#L51) | 51 | `list_online` | 60% |
| [src/infrastructure/repositories/node_repository.py](file:///c:/idle-sense/src/infrastructure/repositories/node_repository.py#L55) | 55 | `list_idle` | 60% |
| [src/infrastructure/repositories/redis_node_repository.py](file:///c:/idle-sense/src/infrastructure/repositories/redis_node_repository.py#L128) | 128 | `list_online` | 60% |
| [src/infrastructure/repositories/redis_node_repository.py](file:///c:/idle-sense/src/infrastructure/repositories/redis_node_repository.py#L134) | 134 | `list_idle` | 60% |
| [src/infrastructure/repositories/sqlite_node_repository.py](file:///c:/idle-sense/src/infrastructure/repositories/sqlite_node_repository.py#L129) | 129 | `list_online` | 60% |
| [src/infrastructure/repositories/sqlite_node_repository.py](file:///c:/idle-sense/src/infrastructure/repositories/sqlite_node_repository.py#L138) | 138 | `list_idle` | 60% |

### 4.11 src/infrastructure/sandbox/ 模块

| 文件路径 | 行号 | 函数/方法名 | 置信度 |
|----------|------|-------------|--------|
| [src/infrastructure/sandbox/sandbox.py](file:///c:/idle-sense/src/infrastructure/sandbox/sandbox.py#L93) | 93 | `_prepare_safe_globals` | 60% |
| [src/infrastructure/sandbox/sandbox.py](file:///c:/idle-sense/src/infrastructure/sandbox/sandbox.py#L894) | 894 | `get_best_available` | 60% |

### 4.12 src/infrastructure/scheduler/ 模块

| 文件路径 | 行号 | 函数/方法名/变量 | 置信度 |
|----------|------|------------------|--------|
| [src/infrastructure/scheduler/models.py](file:///c:/idle-sense/src/infrastructure/scheduler/models.py#L20) | 20 | `DELETED` | 60% |
| [src/infrastructure/scheduler/models.py](file:///c:/idle-sense/src/infrastructure/scheduler/models.py#L94) | 94 | `update_status` | 60% |

### 4.13 src/infrastructure/security/ 模块

| 文件路径 | 行号 | 函数/方法名 | 置信度 |
|----------|------|-------------|--------|
| [src/infrastructure/security/validators.py](file:///c:/idle-sense/src/infrastructure/security/validators.py#L203) | 203 | `validate_task_input` | 60% |
| [src/infrastructure/security/validators.py](file:///c:/idle-sense/src/infrastructure/security/validators.py#L311) | 311 | `validate_user_input` | 60% |
| [src/infrastructure/security/validators.py](file:///c:/idle-sense/src/infrastructure/security/validators.py#L384) | 384 | `add_dangerous_pattern` | 60% |
| [src/infrastructure/security/validators.py](file:///c:/idle-sense/src/infrastructure/security/validators.py#L389) | 389 | `remove_dangerous_pattern` | 60% |

### 4.14 src/infrastructure/utils/ 模块

| 文件路径 | 行号 | 函数/方法名/变量 | 置信度 |
|----------|------|------------------|--------|
| [src/infrastructure/utils/api_utils.py](file:///c:/idle-sense/src/infrastructure/utils/api_utils.py#L315) | 315 | `exc_tb`, `exc_val` | 100% |
| [src/infrastructure/utils/cache_utils.py](file:///c:/idle-sense/src/infrastructure/utils/cache_utils.py#L160) | 160 | `cleanup_expired` | 60% |
| [src/infrastructure/utils/http_pool.py](file:///c:/idle-sense/src/infrastructure/utils/http_pool.py#L82) | 82 | `get_session` | 60% |
| [src/infrastructure/utils/logger.py](file:///c:/idle-sense/src/infrastructure/utils/logger.py#L177) | 177 | `set_level` | 60% |
| [src/infrastructure/utils/logger.py](file:///c:/idle-sense/src/infrastructure/utils/logger.py#L183) | 183 | `get_logger_name` | 60% |

### 4.15 src/presentation/streamlit/ 模块

| 文件路径 | 行号 | 函数/方法名/变量 | 置信度 |
|----------|------|------------------|--------|
| [src/presentation/streamlit/components/sidebar.py](file:///c:/idle-sense/src/presentation/streamlit/components/sidebar.py#L152) | 152 | `resource_allocation` | 60% |
| [src/presentation/streamlit/utils/session_manager.py](file:///c:/idle-sense/src/presentation/streamlit/utils/session_manager.py#L22) | 22 | `LOCAL_STORAGE_KEY` | 60% |
| [src/presentation/streamlit/utils/session_manager.py](file:///c:/idle-sense/src/presentation/streamlit/utils/session_manager.py#L45) | 45 | `get_user_session` | 60% |
| [src/presentation/streamlit/utils/session_manager.py](file:///c:/idle-sense/src/presentation/streamlit/utils/session_manager.py#L59) | 59 | `clear_user_session` | 60% |
| [src/presentation/streamlit/utils/session_manager.py](file:///c:/idle-sense/src/presentation/streamlit/utils/session_manager.py#L66) | 66 | `add_task_to_history` | 60% |
| [src/presentation/streamlit/utils/session_manager.py](file:///c:/idle-sense/src/presentation/streamlit/utils/session_manager.py#L81) | 81 | `get_task_history` | 60% |

---

## 五、未使用的类

### 5.1 src/ 模块

| 文件路径 | 行号 | 类名 | 置信度 |
|----------|------|------|--------|
| 无 | - | - | - |

### 5.2 legacy/ 模块

| 文件路径 | 行号 | 类名 | 置信度 |
|----------|------|------|--------|
| [legacy/websocket_comm/__init__.py](file:///c:/idle-sense/legacy/websocket_comm/__init__.py#L265) | 265 | `NodeWebSocketClient` | 60% |
| [legacy/workflow/__init__.py](file:///c:/idle-sense/legacy/workflow/__init__.py#L171) | 171 | `TaskChain` | 60% |
| [legacy/workflow/__init__.py](file:///c:/idle-sense/legacy/workflow/__init__.py#L331) | 331 | `TaskChord` | 60% |
| [legacy/workflow/__init__.py](file:///c:/idle-sense/legacy/workflow/__init__.py#L401) | 401 | `Workflow` | 60% |
| [legacy/node/base_client.py](file:///c:/idle-sense/legacy/node/base_client.py#L64) | 64 | `BaseNodeClient` | 60% |
| [legacy/checkpoint/__init__.py](file:///c:/idle-sense/legacy/checkpoint/__init__.py#L272) | 272 | `CheckpointableTask` | 60% |
| [legacy/di/__init__.py](file:///c:/idle-sense/legacy/di/__init__.py#L245) | 245 | `Injectable` | 60% |
| [legacy/monitoring/__init__.py](file:///c:/idle-sense/legacy/monitoring/__init__.py#L19) | 19 | `MetricType` | 60% |
| [legacy/event_bus/__init__.py](file:///c:/idle-sense/legacy/event_bus/__init__.py#L298) | 298 | `EventTypes` | 60% |

---

## 六、未使用的变量/常量

### 6.1 config/ 模块

| 文件路径 | 行号 | 变量名 | 置信度 |
|----------|------|--------|--------|
| [config/settings.py](file:///c:/idle-sense/config/settings.py#L133) | 133 | `DEFAULT_STORAGE_SHARE` | 60% |
| [config/settings.py](file:///c:/idle-sense/config/settings.py#L177) | 177 | `MAX_HISTORY` | 60% |
| [config/settings.py](file:///c:/idle-sense/config/settings.py#L183) | 183 | `DEBUG_MODE` | 60% |
| [config/settings.py](file:///c:/idle-sense/config/settings.py#L254) | 254 | `DEFAULT_CHUNK_SIZE` | 60% |
| [config/settings.py](file:///c:/idle-sense/config/settings.py#L260) | 260 | `DEFAULT_MAX_PARALLEL_CHUNKS` | 60% |
| [config/settings.py](file:///c:/idle-sense/config/settings.py#L272) | 272 | `RESULT_TTL` | 60% |
| [config/settings.py](file:///c:/idle-sense/config/settings.py#L290) | 290 | `MAX_CODE_SIZE` | 60% |
| [config/settings.py](file:///c:/idle-sense/config/settings.py#L296) | 296 | `MAX_INPUT_SIZE` | 60% |
| [config/settings.py](file:///c:/idle-sense/config/settings.py#L302) | 302 | `SANDBOX_ENABLED` | 60% |
| [config/settings.py](file:///c:/idle-sense/config/settings.py#L306) | 306 | `NETWORK_ACCESS` | 60% |

### 6.2 src/core/entities/ 模块

| 文件路径 | 行号 | 变量名 | 置信度 |
|----------|------|--------|--------|
| [src/core/entities/folder.py](file:///c:/idle-sense/src/core/entities/folder.py#L38-L40) | 38-40 | `READ`, `WRITE`, `EXECUTE` | 60% |
| [src/core/entities/node.py](file:///c:/idle-sense/src/core/entities/node.py#L37-L39) | 37-39 | `WINDOWS`, `LINUX`, `MACOS` | 60% |

### 6.3 legacy/ 模块 (部分重要项)

| 文件路径 | 行号 | 变量名 | 置信度 |
|----------|------|--------|--------|
| [legacy/api_docs/__init__.py](file:///c:/idle-sense/legacy/api_docs/__init__.py#L14-L18) | 14-18 | `GET`, `POST`, `PUT`, `DELETE`, `PATCH` | 60% |
| [legacy/workflow/__init__.py](file:///c:/idle-sense/legacy/workflow/__init__.py#L45-L47) | 45-47 | `CHAIN`, `GROUP`, `CHORD` | 60% |
| [legacy/websocket_comm/__init__.py](file:///c:/idle-sense/legacy/websocket_comm/__init__.py#L33) | 33 | `NODE_STATUS` | 60% |
| [legacy/token_economy/__init__.py](file:///c:/idle-sense/legacy/token_economy/__init__.py#L27) | 27 | `NATIVE` | 60% |
| [legacy/distributed_task_v2/__init__.py](file:///c:/idle-sense/legacy/distributed_task_v2/__init__.py#L44) | 44 | `SKIPPED` | 60% |

---

## 七、legacy 模块详细未使用代码列表

由于 legacy 模块包含大量未使用代码，以下按子模块分类汇总：

### 7.1 legacy/user_management/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| auth.py | 8 | `register_user`, `login`, `logout`, `get_user_by_username`, `get_quota_by_user_id`, `get_user_by_session`, `change_password`, `verify_permission` |
| local_authorization.py | 3 | `request_folder_creation_authorization`, `confirm_authorization`, `get_operation_logs` |
| models.py | 2 | `set_enforce_limits`, `get_enforce_limits` |
| permission.py | 2 | `validate_task_ownership`, `validate_file_ownership` |
| quota.py | 7 | `check_quota`, `consume_quota`, `release_quota`, `set_user_quota`, `get_user_quota`, `reset_daily_usage`, `get_usage_stats` |

### 7.2 legacy/token_economy/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 10+ | `update_congestion`, `estimate_resources`, `decay_reputation`, `get_trust_score`, `get_history`, `get_reputation`, `get_stake_info`, `deposit`, `withdraw`, `create_task_payment`, `reward_worker`, `penalize_worker`, `finalize_task`, `get_balance` |

### 7.3 legacy/distributed_task_v2/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| dag_engine.py | 1 | `recover_from_checkpoint` |
| data_locality.py | 10+ | `record_access`, `has_data`, `distance_to`, `unregister_node`, `register_data`, `unregister_data`, `select_best_node`, `get_locality_recommendations`, `optimize_data_placement`, `get_data_stats` |
| fault_tolerance.py | 2 | `execute_speculative`, `recover_from_checkpoint` |
| progress_ws.py | 10+ | `register_task`, `register_stage`, `update_task_status`, `update_stage_progress`, `complete_chunk`, `fail_chunk`, `unsubscribe`, `get_stage_progress`, `get_history` |
| shuffle.py | 5+ | `start_shuffle`, `add_data`, `assign_partition`, `execute_shuffle`, `receive_shuffle_data` |

### 7.4 legacy/p2p_network/

| 文件 | 未使用方法数量 | 说明 |
|------|---------------|------|
| __init__.py | 5+ | DHT 相关方法 |
| bandwidth.py | 3+ | 带宽统计相关 |
| reputation.py | 多个 | 声誉系统相关 |

### 7.5 legacy/task_deps/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 15+ | `remove_dependency`, `remove_node`, `get_dependencies`, `get_dependents`, `has_cycle`, `get_critical_path`, `subgraph`, `get_blocked_tasks`, `get_parallelism_level`, `register_task`, `get_execution_plan`, `get_next_batch`, `mark_failed`, `get_task_data`, `visualize` |

### 7.6 legacy/task_queue/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 5+ | `peek` (多个类), `unregister_handler`, `start_workers`, `stop_workers` |

### 7.7 legacy/task_scheduler/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 10+ | `schedule_once`, `schedule_interval`, `schedule_cron`, `schedule_daily`, `unschedule`, `get_all_tasks`, `get_tasks_by_tag`, `pause_task`, `resume_task`, `run_task_now`, `set_callbacks`, `get_upcoming_runs` |

### 7.8 legacy/cache/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 8+ | `invalidate_tag`, `remember`, `forget`, `has`, `decrement`, `get_cache`, `clear_all`, `stats_all` |

### 7.9 legacy/di/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 10+ | `register_singleton`, `register_transient`, `register_scoped`, `register_instance`, `try_resolve`, `clear_scoped`, `clear_all`, `injectable`, `get_container`, `configure_container` |

### 7.10 legacy/event_bus/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 5+ | `on`, `unsubscribe`, `publish_async`, `get_history`, `get_event_bus` |

### 7.11 legacy/health_check/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 5+ | `register_check`, `remove_check`, `register_checker`, `unregister_checker`, `add_callback` |

### 7.12 legacy/load_balancer/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 10+ | `set_key_extractor`, `record_result`, `remove_node`, `get_healthy_nodes`, `select_node`, `record_request_start`, `record_request_end`, `set_health_checker`, `start_health_checks`, `stop_health_checks`, `drain_node`, `reset_stats` |

### 7.13 legacy/message_queue/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 10+ | `get_pending` (多个类), `unsubscribe`, `request_reply`, `start_consumers`, `stop_consumers`, `get_subscriptions` |

### 7.14 legacy/monitoring/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 8+ | `unregister`, `record_task_submitted`, `record_task_completed`, `update_task_counts`, `update_node_counts`, `record_scheduler_latency`, `setup_metrics_endpoint` |

### 7.15 legacy/distributed_lock/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 5+ | `get_all_locks` (多个类), `release_all`, `acquire_context` |

### 7.16 legacy/diagnostics/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 5+ | `unregister`, `create_health_endpoint`, `liveness`, `readiness`, `detailed_health`, `diagnostics` |

### 7.17 legacy/connection_pool/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 5+ | `resize`, `get_pool`, `create_socket_pool`, `get_all_stats`, `close_all` |

### 7.18 legacy/migration/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 6+ | `transaction` (多个类), `is_applied`, `create_migration`, `migrate`, `rollback` |

### 7.19 legacy/config_validator/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 5+ | `set_env_prefix`, `register_schema`, `register_custom_validator`, `validate_config`, `validate_env`, `validate_file` |

### 7.20 legacy/checkpoint/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 8+ | `get_checkpoint_history`, `delete_checkpoint`, `should_checkpoint`, `should_resume`, `get_resume_state`, `clear_checkpoints`, `with_checkpoint` |

### 7.21 legacy/callbacks/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 6+ | `on_start`, `on_complete`, `register_task_callback`, `trigger`, `trigger_async`, `clear_task_callbacks` |

### 7.22 legacy/benchmark/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 1 | `compare_suites` |

### 7.23 legacy/api_docs/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 6+ | `scan_module`, `scan_class`, `register_model`, `generate_swagger_html`, `generate_redoc_html`, `to_yaml` |

### 7.24 legacy/logging_config/

| 文件 | 未使用方法数量 | 主要未使用方法 |
|------|---------------|----------------|
| __init__.py | 4+ | `setup_logging`, `log_exception`, `suppress_logging`, `verbose_logging` |

### 7.25 其他 legacy 模块

| 模块 | 未使用代码数量 | 说明 |
|------|---------------|------|
| legacy/test_generator/ | 10+ | 测试生成器相关方法 |
| legacy/timeout_manager/ | 6+ | 超时管理相关方法 |
| legacy/resource_estimator/ | 若干 | 资源估算相关 |
| legacy/rate_limiter/ | 若干 | 速率限制相关 |
| legacy/result_aggregator/ | 若干 | 结果聚合相关 |
| legacy/retry_recovery/ | 若干 | 重试恢复相关 |
| legacy/retry_strategy/ | 若干 | 重试策略相关 |
| legacy/profiler/ | 若干 | 性能分析相关 |
| legacy/plugins/ | 若干 | 插件系统相关 |
| legacy/priority_queue/ | 若干 | 优先队列相关 |

---

## 八、注释掉的代码块

经过扫描，项目中未发现明显的注释掉的代码块（如 `# def ...`、`# class ...`、`# return ...` 等模式）。

---

## 九、建议与结论

### 9.1 高优先级清理建议

1. **未使用的导入语句**：建议立即清理，可使用 `ruff check --fix --select F401 .` 自动修复
2. **未使用的局部变量**：建议清理或使用 `_` 替代未使用的变量名
3. **src/ 模块中的未使用代码**：建议评估后删除，这些是当前活跃代码

### 9.2 中优先级清理建议

1. **config/settings.py 中的未使用变量**：可能是预留配置，建议确认后处理
2. **src/core/interfaces/ 中的未使用方法**：可能是接口定义，需确认是否有实现类使用

### 9.3 低优先级清理建议

1. **legacy/ 模块中的大量未使用代码**：
   - 该模块似乎是旧版代码或实验性代码
   - 建议整体评估是否需要保留整个模块
   - 如果确定不再使用，可考虑删除整个 legacy 目录

### 9.4 特殊说明

1. **sandbox.py 中的可选导入**：`wasmer`, `wasmtime`, `pyodide`, `rustpython` 等是可选依赖检测导入，不建议删除
2. **测试文件中的未使用导入**：可能是测试框架需要或预留的测试工具，建议谨慎处理
3. **model_config 变量**：Pydantic v2 的配置，可能是框架需要，不建议删除

---

**报告生成完成**

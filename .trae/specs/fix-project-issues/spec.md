# 项目问题修复 Spec

## Why

项目健康检查发现多个代码质量问题，包括1个运行时错误风险（未定义变量）、3个测试失败、多个代码风格问题和安全隐患，需要系统性修复以提升项目稳定性和代码质量。

## What Changes

* 修复 `simple_server.py:890` 的 `_shutdown_persistent_storage` 未定义变量（**运行时错误风险**）

* 修复 3 个失败测试（配置默认值不一致：测试期望 `memory`，实际为 `file`）

* 移除未使用的导入（F401）- `container.py` 等

* 修复导入位置错误（E402）- 约8处

* 修复未使用循环变量（B007）- 约8处

* 清理空白行空格（W293）- 可自动修复

* 简化代码结构（SIM建议）- 可自动修复

## Impact

* Affected specs: 无（独立修复任务）

* Affected code:

  * `legacy/scheduler/simple_server.py` - 未定义变量、E402、B007、W293

  * `src/di/container.py` - F401未使用导入

  * `src/presentation/streamlit/utils/session_manager.py` - 默认配置值

  * `tests/unit/test_session_manager.py` - 测试期望值

  * 其他包含 E402/B007/W293/SIM 问题的文件

## ADDED Requirements

### Requirement: 修复未定义变量错误

系统 SHALL 确保 `legacy/scheduler/simple_server.py` 中 `_shutdown_persistent_storage` 函数在 `atexit.register()` 调用之前定义，避免运行时 NameError。

#### Scenario: 函数定义顺序正确

* **WHEN** 模块加载执行到 `atexit.register(_shutdown_persistent_storage)`

* **THEN** `_shutdown_persistent_storage` 已被定义，不会抛出 NameError

### Requirement: 统一配置默认值

系统 SHALL 确保会话配置默认值与测试期望一致。

#### Scenario: 测试通过

* **WHEN** 运行 `test_default_config`, `test_from_env_default`, `test_default_backend_is_memory`

* **THEN** 所有测试通过，默认后端类型为 `memory`

### Requirement: 清理代码风格问题

系统 SHALL 通过 ruff 自动修复或手动修复以下代码风格问题：

* F401: 移除所有未使用的导入

* E402: 将模块级导入移至文件顶部

* B007: 使用 `_` 替换未使用的循环变量

* W293: 移除空白行中的空格

* SIM: 简化可简化的代码结构

#### Scenario: ruff check 通过

* **WHEN** 运行 `ruff check src/ legacy/ --select F821,F401,E402,B007,W293`

* **THEN** 输出无错误

## MODIFIED Requirements

### Requirement: 会话管理器默认配置

将 `SessionConfig.backend_type` 的默认值从 `"file"` 改为 `"memory"`，与测试期望保持一致。
同时更新 `SessionConfig.from_env()` 的环境变量默认值为 `"memory"`。

## REMOVED Requirements

保持原有功能正常运行


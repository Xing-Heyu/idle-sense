# Tasks

## Phase 1: 高优先级修复 (P0) - 影响功能

- [x] Task 1.1: 修复 `simple_server.py` 未定义变量 `_shutdown_persistent_storage`
  - [x] SubTask 1.1.1: 将 `_shutdown_persistent_storage` 函数定义移到 `atexit.register()` 调用之前（第905行移到890行之前）
  - [x] SubTask 1.1.2: 验证函数逻辑正确性不变

- [x] Task 1.2: 修复会话配置默认值不一致（3个失败测试）
  - [x] SubTask 1.2.1: 修改 `session_manager.py` 中 `SessionConfig.backend_type` 默认值从 `"file"` 改为 `"memory"`
  - [x] SubTask 1.2.2: 修改 `SessionConfig.from_env()` 环境变量默认值从 `"file"` 改为 `"memory"`
  - [x] SubTask 1.2.3: 运行失败测试确认通过（3个测试全部通过）

## Phase 2: 中优先级修复 (P1) - 代码质量

- [x] Task 2.1: 移除未使用的导入 (F401)
  - [x] SubTask 2.1.1: 修复 `src/di/container.py` 的 F401 问题
  - [x] SubTask 2.1.2: 运行 `ruff check --select F401` 检查所有文件并修复

- [x] Task 2.2: 修复导入位置错误 (E402)
  - [x] SubTask 2.2.1: 运行 `ruff check --select E402` 定位所有E402问题
  - [x] SubTask 2.2.2: 逐个修复导入位置问题（16处）

- [x] Task 2.3: 修复未使用循环变量 (B007)
  - [x] SubTask 2.3.1: 运行 `ruff check --select B007` 定位所有B007问题
  - [x] SubTask 2.3.2: 将未使用的循环变量替换为 `_`

## Phase 3: 低优先级修复 (P2) - 风格优化

- [x] Task 3.1: 清理空白行空格 (W293)
  - [x] SubTask 3.1.1: 运行 `ruff check --fix --select W293` 自动修复（121处）

- [x] Task 3.2: 简化代码结构 (SIM)
  - [x] SubTask 3.2.1: 运行 `ruff check --fix --select SIM` 自动修复可简化代码（25/26处）

## Phase 4: 验证

- [x] Task 4.1: 运行完整测试套件确认无回归
  - [x] SubTask 4.1.1: 运行 `python -m pytest tests/unit/ -q --tb=short`
  - [x] SubTask 4.1.2: 确认之前失败的3个测试现在通过
  - [x] SubTask 4.1.3: 确认无新增失败测试（826 passed, 0 failed, 2 skipped）

- [x] Task 4.2: 运行 ruff 检查确认所有问题已修复
  - [x] SubTask 4.2.1: 运行 `python -m ruff check src/ legacy/ --output-format=concise`
  - [x] SubTask 4.2.2: 确认 F821, F401, E402, B007, W293 错误数为0（All checks passed!）

# Task Dependencies
- [Task 1.2] 无依赖，可与 Task 1.1 并行
- [Task 2.1, Task 2.2, Task 2.3] 可并行执行
- [Task 3.1, Task 3.2] 可并行执行
- [Task 4.1, Task 4.2] 依赖所有修复任务完成

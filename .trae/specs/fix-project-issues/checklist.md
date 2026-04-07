# 项目问题修复检查清单

## Phase 1: 高优先级修复 (P0)

### H1: 未定义变量修复
- [x] `_shutdown_persistent_storage` 函数定义已移到 `atexit.register()` 调用之前
- [x] 函数逻辑保持不变（仍能正确关闭持久化存储）
- [x] `ruff check --select F821` 无错误

### H2: 配置默认值统一
- [x] `SessionConfig.backend_type` 默认值已改为 `"memory"`
- [x] `SessionConfig.from_env()` 环境变量默认值已改为 `"memory"`
- [x] `test_default_config` 测试通过
- [x] `test_from_env_default` 测试通过
- [x] `test_default_backend_is_memory` 测试通过

## Phase 2: 中优先级修复 (P1)

### M1: F401 未使用导入清理
- [x] `src/di/container.py` 的未使用导入已移除（ensure_data_dirs, FileSessionBackend）
- [x] 所有文件的 F401 问题已修复（共7处）
- [x] `ruff check --select F401` 无错误

### M2: E402 导入位置修复
- [x] 所有模块级导入已移至文件顶部（16处）
- [x] `ruff check --select E402` 无错误

### M3: B007 循环变量修复
- [x] 所有未使用的循环变量已替换为 `_`（7处）
- [x] `ruff check --select B007` 无错误

## Phase 3: 低优先级修复 (P2)

### L1: W293 空白行空格清理
- [x] 空白行中的空格已清理（121处）
- [x] `ruff check --select W293` 无错误

### L2: SIM 代码简化
- [x] 可简化的代码结构已优化（25/26处，剩余1处SIM117需手动处理）
- [x] `ruff check --select SIM` 仅剩建议性提示

## Phase 4: 验证

### V1: 测试验证
- [x] 单元测试全部通过（826 passed, 0 failed, 2 skipped）
- [x] 之前失败的3个测试现在通过
- [x] 无新增回归测试失败

### V2: 代码质量验证
- [x] `ruff check src/ legacy/` 高优先级错误(F821, F401)为0
- [x] 中优先级错误(E402, B007)为0
- [x] W293 空白行错误为0

## 问题修复统计

| 严重程度 | 问题类型 | 发现数量 | 已修复 | 状态 |
|---------|---------|---------|--------|------|
| 🔴 高 | F821 未定义变量 | 1 | 1 | ✅ |
| 🔴 高 | 测试失败 | 3 | 3 | ✅ |
| 🟡 中 | F401 未使用导入 | 7 | 7 | ✅ |
| 🟡 中 | E402 导入位置 | 16 | 16 | ✅ |
| 🟡 中 | B007 循环变量 | 7 | 7 | ✅ |
| 🟢 低 | W293 空白行空格 | 121 | 121 | ✅ |
| 🟢 低 | SIM 代码简化 | 26 | 25 | ⚠️ (1处需手动) |
| **总计** | | **181** | **180** | **99.4%** |

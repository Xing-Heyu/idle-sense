# Tasks

## Phase 1: P0 极简修复（5分钟级）

- [x] Task 1.1: `.gitignore` 添加数据库排除规则
  - [x] 1.1.1 在 `.gitignore` 中添加 `*.db` 规则
  - [x] 1.1.2 验证 `audit.db` 不再被 git 跟踪

- [x] Task 1.2: 限流器异常添加警告日志
  - [x] 1.2.1 修改 `src/infrastructure/security/rate_limiter.py` 第62-65行，将 `except ImportError: pass` 改为 `except ImportError: logging.warning(...)`，将 `except Exception: pass` 改为 `except Exception: logging.warning(...)`
  - [x] 1.2.2 确保模块顶部有 `import logging` 和 `logger = logging.getLogger(__name__)`

## Phase 2: P1 配置一致性修复

- [x] Task 2.1: CORS 配置可配置化
  - [x] 2.1.1 修改 `legacy/scheduler/simple_server.py` 第1196-1208行，从环境变量 `CORS_ALLOWED_ORIGINS` 读取允许的来源列表
  - [x] 2.1.2 当 `allow_origins=["*"]` 时设置 `allow_credentials=False`（浏览器规范要求）
  - [x] 2.1.3 当指定具体域名时设置 `allow_credentials=True`
  - [x] 2.1.4 在 `config/.env.example` 中添加 `CORS_ALLOWED_ORIGINS=*` 配置项及说明

- [x] Task 2.2: 消除幽灵配置
  - [x] 2.2.1 从 `config/.env.example` 中删除 `REQUIRE_AUTH=false` 和 `ALLOWED_ORIGINS=*`
  - [x] 2.2.2 从 `docs/DEPLOYMENT.md` 中删除 `REQUIRE_AUTH` 和 `ALLOWED_ORIGINS` 相关说明
  - [x] 2.2.3 从 `scripts/setup_scheduler.sh` 中删除 `REQUIRE_AUTH=false` 和 `ALLOWED_ORIGINS=*` 行

- [x] Task 2.3: CI 质量门禁生效
  - [x] 2.3.1 修改 `.github/workflows/ci.yml`，移除所有 `|| true` 容错设置
  - [x] 2.3.2 修改安全扫描步骤的 `exit-code` 从 `0` 改为 `1`
  - [x] 2.3.3 统一 CI 矩阵中的 Python 版本，移除 3.8（仅保留 3.9, 3.10, 3.11）

- [x] Task 2.4: 统一 Python 版本声明
  - [x] 2.4.1 确认 `pyproject.toml` 中 `requires-python` 为 `>=3.9`
  - [x] 2.4.2 确认 CI 矩阵移除 Python 3.8（在 Task 2.3 中一并完成）

## Phase 3: P2 技术债修复

- [x] Task 3.1: 修复 TokenEncryption salt 一致性
  - [x] 3.1.1 分析 `src/core/services/token_encryption_service.py` 的加密/解密流程
  - [x] 3.1.2 添加 `salt_file` 参数，优先从 salt 文件读取已有 salt
  - [x] 3.1.3 不存在 salt 文件时生成新 salt 并持久化到文件
  - [x] 3.1.4 确保向后兼容：不提供 salt_file 时行为不变

- [x] Task 3.2: 修复 lru_cache + 可变 Settings
  - [x] 3.2.1 修改 `config/settings.py` 中的 `get_settings()` 函数，精简 docstring
  - [x] 3.2.2 添加 `clear_settings_cache()` 函数供外部调用
  - [x] 3.2.3 将 `clear_settings_cache` 加入 `__all__` 导出列表

## Phase 4: 验证

- [x] Task 4.1: 运行测试确认无回归
  - [x] 4.1.1 运行 `python -m pytest tests/unit/ -q --tb=short`
  - [x] 4.1.2 确认所有测试通过（826 passed, 2 skipped, 0 failed）

- [x] Task 4.2: 手动验证关键修复
  - [x] 4.2.1 验证 `.gitignore` 排除 `.db` 文件
  - [x] 4.2.2 验证 CORS 环境变量读取逻辑正确
  - [x] 4.2.3 验证幽灵配置已从所有文件中移除
  - [x] 4.2.4 验证 CI 配置不再有容错设置

# Task Dependencies
- [Task 1.1, Task 1.2] 无依赖，可并行执行
- [Task 2.1, Task 2.2] 可并行执行
- [Task 2.3, Task 2.4] 合并执行
- [Task 3.1, Task 3.2] 无依赖，可并行执行
- [Task 4.1, Task 4.2] 依赖所有修复任务完成

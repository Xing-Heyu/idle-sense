# 双轮评估问题修复 Spec

## Why
双轮系统性评估验证了原检查报告中 48 个问题的真实性，确认 44/48 真实存在，3 个需修正描述，1 个判断错误。根据项目当前阶段（Beta PoC / 单人开发 / 无公网暴露），筛选出当前阶段真正需要修复的问题，避免过度修复。

## What Changes
- `.gitignore` 添加 `*.db` 排除规则，防止数据库文件被 git 跟踪
- 限流器 `rate_limiter.py` 异常处理添加 `logging.warning`，避免限流静默失效
- CORS 配置从硬编码 `allow_origins=["*"]` 改为读取环境变量，开发环境默认 `*`，生产环境可限定域名
- 删除 `REQUIRE_AUTH` 和 `ALLOWED_ORIGINS` 幽灵配置（存在于 .env.example 和文档但从未被代码读取），消除虚假安全感
- CI 流水线移除 `|| true` 和 `exit-code: 0`，让质量门禁真正生效
- 统一 Python 版本声明为 `>=3.9`，消除 CI 矩阵与 pyproject.toml 的矛盾
- 修复 `TokenEncryption._derive_keys_from_password` 每次生成新 salt 导致重启后旧数据无法解密的问题
- 修复 `lru_cache` + 可变 Settings 导致配置变更不生效的问题

## Impact
- Affected specs: 安全配置、CI/CD 流水线、代币加密服务、配置管理
- Affected code:
  - `.gitignore`
  - `src/infrastructure/security/rate_limiter.py`
  - `legacy/scheduler/simple_server.py`
  - `config/.env.example`
  - `docs/DEPLOYMENT.md`
  - `scripts/setup_scheduler.sh`
  - `.github/workflows/ci.yml`
  - `.github/workflows/ci.yml` (Python 版本矩阵)
  - `src/infrastructure/security/token_encryption_service.py`
  - `config/settings.py`

## ADDED Requirements

### Requirement: 数据库文件排除
系统 SHALL 在 `.gitignore` 中排除所有 `.db` 文件，防止 SQLite 数据库被提交到版本库。

#### Scenario: 数据库文件不被跟踪
- **WHEN** 开发者运行 `git status`
- **THEN** `audit.db` 及其他 `.db` 文件不出现在未跟踪文件列表中

### Requirement: 限流器异常可见
系统 SHALL 在限流器初始化失败时记录警告日志，而非静默吞没异常。

#### Scenario: slowapi 未安装
- **WHEN** slowapi 库未安装导致 ImportError
- **THEN** 系统记录 `logging.warning` 级别日志，明确提示限流功能不可用

#### Scenario: 限流器运行时异常
- **WHEN** 限流器运行时发生非 ImportError 异常
- **THEN** 系统记录 `logging.warning` 级别日志，包含异常详情

### Requirement: CORS 可配置化
系统 SHALL 从环境变量读取 CORS 允许的来源列表，开发环境默认允许所有来源，生产环境可限定域名。

#### Scenario: 开发环境
- **WHEN** 未设置 `CORS_ALLOWED_ORIGINS` 环境变量
- **THEN** CORS 配置为 `allow_origins=["*"]`，`allow_credentials=False`

#### Scenario: 生产环境
- **WHEN** 设置 `CORS_ALLOWED_ORIGINS=http://localhost:8501,https://example.com`
- **THEN** CORS 配置为指定的域名列表，`allow_credentials=True`

### Requirement: 消除幽灵配置
系统 SHALL 移除从未被代码读取的 `REQUIRE_AUTH` 和 `ALLOWED_ORIGINS` 配置项，避免给用户造成虚假安全感。

#### Scenario: 配置文件清理
- **WHEN** 开发者查看 `.env.example`
- **THEN** 不存在 `REQUIRE_AUTH` 和 `ALLOWED_ORIGINS` 配置项

### Requirement: CI 质量门禁生效
系统 SHALL 在 CI 流水线中移除所有 `|| true` 和 `exit-code: 0` 容错设置，使代码质量检查、测试和安全扫描的失败能真正阻止流水线。

#### Scenario: Lint 检查失败
- **WHEN** ruff 检查发现代码质量问题
- **THEN** CI 流水线失败并阻止合并

#### Scenario: 测试失败
- **WHEN** pytest 测试用例失败
- **THEN** CI 流水线失败并阻止合并

### Requirement: Python 版本声明一致
系统 SHALL 在 `pyproject.toml` 和 CI 矩阵中统一 Python 版本要求为 `>=3.9`。

#### Scenario: CI 矩阵与项目声明一致
- **WHEN** 查看 CI 配置的 Python 版本矩阵
- **THEN** 不包含 Python 3.8

### Requirement: TokenEncryption salt 一致性
系统 SHALL 在加密时将 salt 与密文一起存储，解密时使用存储的 salt，确保重启服务后旧数据可正确解密。

#### Scenario: 加密后重启解密
- **WHEN** 使用 TokenEncryption 加密数据后重启服务
- **THEN** 使用相同密码可正确解密之前加密的数据

### Requirement: Settings 配置变更即时生效
系统 SHALL 在配置变更时使缓存失效，确保 `lru_cache` 不会缓存过期的 Settings 对象。

#### Scenario: 修改环境变量后配置生效
- **WHEN** 修改环境变量并重新获取 Settings 实例
- **THEN** 新实例反映最新的环境变量值

## MODIFIED Requirements

### Requirement: CORS 安全配置
原硬编码 `allow_origins=["*"]` + `allow_credentials=True` 修改为从环境变量读取，且 `allow_origins=["*"]` 时自动设置 `allow_credentials=False`（符合浏览器安全规范）。

## REMOVED Requirements

### Requirement: REQUIRE_AUTH 配置开关
**Reason**: 该配置从未被任何 Python 代码读取，设置 `REQUIRE_AUTH=true` 不会产生任何效果，给用户造成虚假安全感。认证功能应在真正实现时再添加配置项。
**Migration**: 未来实现认证功能时，在 `SecuritySettings` 中添加 `require_auth` 字段并实际接入鉴权逻辑。

### Requirement: ALLOWED_ORIGINS 配置项
**Reason**: 该配置从未被任何 Python 代码读取，CORS 配置硬编码在 simple_server.py 中。已由 `CORS_ALLOWED_ORIGINS` 环境变量替代。
**Migration**: 使用新的 `CORS_ALLOWED_ORIGINS` 环境变量。

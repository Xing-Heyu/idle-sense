# 修复关键生产问题 Spec

## Why
当前系统存在多个真实的生产环境问题，包括安全漏洞（WASM沙箱exec执行）、性能瓶颈（无分页查询）、并发风险（SQLite单连接）和资源泄漏风险（Firecracker变量定义），这些问题可能导致安全事件、性能下降或系统不稳定。

## What Changes
- **移除或严格限制 WASM 沙箱中的 exec() 调用**（P0 安全问题）
- **为节点仓储添加分页支持**（P1 性能问题）
- **为所有 SQLite 仓储实现连接池**（P1 并发问题）
- **修复 Firecracker 边缘资源泄漏**（P2 稳定性问题）

## Impact
- Affected specs: 无直接影响其他规格
- Affected code:
  - src/infrastructure/sandbox/sandbox.py（P0, P2）
  - src/infrastructure/repositories/sqlite_node_repository.py（P1）
  - src/infrastructure/repositories/sqlite_token_repository.py（P1）
  - src/infrastructure/repositories/sqlite_task_repository.py（P1）

## ADDED Requirements

### Requirement: 安全的 WASM 执行环境
系统 SHALL 提供安全的 WASM 沙箱执行环境，禁止直接使用 exec() 执行任意 Python 代码。

#### Scenario: 移除危险的 exec() 调用
- **WHEN** WASM 沙箱需要执行用户代码时
- **THEN** 系统 SHALL 使用白名单机制或完全移除 exec() 调用，防止代码注入攻击

### Requirement: 分页查询支持
节点仓储 SHALL 支持分页查询，避免一次性加载大量数据导致内存溢出。

#### Scenario: 带分页的列表查询
- **WHEN** 用户请求节点列表时
- **THEN** 系统 SHALL 支持 limit 和 offset 参数，返回指定范围的数据

### Requirement: SQLite 连接池
所有 SQLite 仓储 SHALL 使用连接池管理数据库连接，支持并发访问。

#### Scenario: 并发数据库操作
- **WHEN** 多个协程同时访问数据库时
- **THEN** 每个 SHALL 操作使用独立的连接，避免并发冲突

### Requirement: Firecracker 资源管理
Firecracker 沙箱 SHALL 正确管理临时资源，确保异常情况下也能清理。

#### Scenario: 异常时的资源清理
- **WHEN** Firecracker 执行过程中发生异常时
- **THEN** 所有临时文件和进程 SHALL 被正确清理，避免资源泄漏

## MODIFIED Requirements

### Requirement: 节点仓储接口
修改 INodeRepository 接口，添加分页参数支持。

```python
async def list_all(self, limit: int = 100, offset: int = 0) -> list[Node]
async def list_by_status(self, status: NodeStatus, limit: int = 100, offset: int = 0) -> list[Node]
```

### Requirement: SQLite 仓储基类
所有 SQLite 仓储 SHALL 继承统一的基类，实现连接池逻辑。

## REMOVED Requirements

### Requirement: 危险的 exec() 执行
**Reason**: 存在严重的安全漏洞，允许执行任意 Python 代码
**Migration**: 完全移除或替换为安全的沙箱执行机制

# Tasks

## P0: 修复 WASM 沙箱安全问题（最高优先级）

- [x] Task 1: 分析并移除/限制 sandbox.py:713 的 exec() 调用
  - [x] 1.1 评估 exec() 的使用场景和安全风险
  - [x] 1.2 实现安全的替代方案（白名单/AST解析/完全移除）
  - [ ] 1.3 更新相关测试用例验证安全性
  - [x] 1.4 添加安全警告日志

## P1: 优化数据访问层（高优先级）

- [ ] Task 2: 为 sqlite_node_repository.py 添加分页支持
  - [ ] 2.1 修改 list_all(), list_by_status(), list_online(), list_idle() 方法签名
  - [ ] 2.2 在 SQL 查询中添加 LIMIT 和 OFFSET 子句
  - [ ] 2.3 添加分页参数校验（防止负值或过大值）
  - [ ] 2.4 更新调用方适配新的分页接口

- [x] Task 3: 实现 SQLite 连接池
  - [x] 3.1 创建 SQLiteConnectionPool 基类（支持 aiosqlite）
  - [x] 3.2 重构 sqlite_node_repository.py 使用连接池
  - [x] 3.3 重构 sqlite_token_repository.py 使用连接池
  - [x] 3.4 重构 sqlite_task_repository.py 使用连接池
  - [x] 3.5 添加连接池配置（最大连接数、超时等）
  - [ ] 3.6 测试并发场景下的连接池行为

## P2: 修复资源泄漏问题（中优先级）

- [x] Task 4: 修复 Firecracker 变量定义位置
  - [x] 4.1 将 vm_id, socket_path, code_file 变量定义移到 try 块之前
  - [x] 4.2 确保 finally 块能正确清理所有临时资源
  - [ ] 4.3 添加资源清理的单元测试

# Task Dependencies
- [Task 2] 和 [Task 3] 可以并行执行
- [Task 4] 独立执行，与其他任务无依赖
- [Task 1] 应优先完成（P0 安全问题）

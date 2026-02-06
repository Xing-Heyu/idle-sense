markdown
# 系统架构文档

## 🏗️ 整体架构概述

闲置计算加速器是一个分布式计算框架，通过利用个人电脑的闲置计算资源来执行计算任务。系统采用客户端-服务器架构，包含三个核心组件。

### 架构图
┌─────────────────┐ ┌──────────────────┐ ┌─────────────────┐
│ 用户界面 │ │ 调度中心 │ │ 计算节点 │
│ │ │ │ │ │
│ • 任务提交 │◄──►│ • 任务队列 │◄──►│ • 闲置检测 │
│ • 结果查看 │ │ • 节点管理 │ │ • 安全执行 │
│ • 状态监控 │ │ • 结果存储 │ │ • 资源清理 │
└─────────────────┘ └──────────────────┘ └─────────────────┘
│ │ │
▼ ▼ ▼
┌─────────────────┐ ┌──────────────────┐ ┌─────────────────┐
│ Web浏览器 │ │ FastAPI服务 │ │ 本地计算机 │
│ Streamlit │ │ Uvicorn服务器 │ │ 系统资源 │
└─────────────────┘ └──────────────────┘ └─────────────────┘

text

## 🔄 数据流说明

### 1. 任务提交阶段
用户 → 网页界面 → 调度中心 → 生成任务ID → 返回用户

text

**详细步骤**:
1. 用户在网页界面输入Python代码
2. 网页界面通过HTTP POST发送到调度中心
3. 调度中心验证代码并生成唯一任务ID
4. 任务加入待处理队列
5. 返回任务ID给用户

### 2. 任务分配阶段
计算节点 → 定期检查 → 请求任务 → 调度中心 → 分配任务 → 返回代码

text

**详细步骤**:
1. 计算节点定期检查自身闲置状态
2. 如果闲置，向调度中心请求任务
3. 调度中心从队列取出待处理任务
4. 将任务标记为"执行中"
5. 返回任务代码给计算节点

### 3. 任务执行阶段
计算节点 → 安全沙箱 → 执行代码 → 捕获输出 → 生成结果

text

**详细步骤**:
1. 计算节点创建安全执行环境
2. 在隔离环境中运行Python代码
3. 捕获标准输出和错误
4. 限制执行时间和资源使用
5. 生成执行结果

### 4. 结果返回阶段
计算节点 → 提交结果 → 调度中心 → 更新状态 → 用户查询

text

**详细步骤**:
1. 计算节点将结果提交到调度中心
2. 调度中心更新任务状态为"已完成"
3. 存储执行结果
4. 用户可以通过任务ID查询结果

## 📦 核心组件

### idle-sense（闲置检测库）

#### 功能职责
- 跨平台系统状态监控
- 智能闲置判定算法
- 资源使用率收集
- 平台特定API封装

#### 模块结构
idle_sense/
├── core.py # 跨平台统一接口
├── windows.py # Windows平台实现
├── macos.py # macOS平台实现
├── linux.py # Linux平台实现（预留）
└── init.py # 包定义和导出

text

#### 接口定义
```python
# 核心接口示例
def is_idle(idle_threshold_sec=300) -> bool:
    """判断系统是否处于闲置状态"""
    pass

def get_system_status() -> dict:
    """获取系统当前状态信息"""
    pass

def get_platform() -> str:
    """获取当前平台名称"""
    pass
调度中心（Scheduler）
功能职责
任务队列管理

计算节点注册和状态跟踪

任务分配和调度

结果存储和查询

API服务提供

技术栈
Web框架: FastAPI

服务器: Uvicorn

数据存储: 内存存储（可扩展为Redis）

API文档: OpenAPI自动生成

核心数据结构
python
# 任务信息结构
{
    "task_id": "uuid或自增ID",
    "code": "Python代码字符串",
    "status": "pending|running|completed|failed",
    "created_at": "时间戳",
    "completed_at": "时间戳（可选）",
    "result": "执行结果（可选）"
}

# 节点信息结构
{
    "node_id": "节点唯一标识",
    "status": "idle|busy|offline",
    "resources": {
        "cpu_cores": 8,
        "memory_mb": 16384
    },
    "last_heartbeat": "最后心跳时间"
}
计算节点（Node）
功能职责
系统闲置状态检测

任务请求和执行

安全沙箱环境管理

资源使用限制

心跳报告和维护

执行流程
python
def node_main_loop():
    while True:
        # 1. 检测是否闲置
        if is_system_idle():
            # 2. 请求任务
            task = request_task_from_scheduler()
            
            if task:
                # 3. 安全执行
                result = execute_safely(task.code)
                
                # 4. 提交结果
                submit_result(task.id, result)
        
        # 5. 等待下次检查
        sleep(check_interval)
安全特性
代码执行时间限制

内存使用限制

网络访问控制

文件系统隔离

自动资源清理

🛡️ 安全架构
执行环境隔离
text
计算节点进程
    ├── 主进程（监控）
    └── 子进程（执行沙箱）
        ├── 资源限制（CPU/内存/时间）
        ├── 文件系统隔离（临时目录）
        └── 网络访问控制（默认禁止）
安全措施
代码审查: 基本语法检查和长度限制

资源限制: 防止资源耗尽攻击

进程隔离: 防止系统级影响

自动清理: 任务完成即删除临时文件

输入验证: 防止注入攻击

安全配置示例
yaml
security:
  max_task_time: 300          # 最大执行时间（秒）
  max_memory_mb: 1024         # 最大内存使用（MB）
  max_disk_mb: 100            # 最大磁盘使用（MB）
  network_access: false       # 是否允许网络访问
  allowed_modules:            # 允许导入的模块
    - math
    - random
    - datetime
🔌 通信协议
HTTP API
协议: HTTP/1.1

数据格式: JSON

编码: UTF-8

超时: 默认10秒

接口端点
text
# 任务管理
POST   /submit           # 提交任务
GET    /get_task         # 获取任务
POST   /submit_result    # 提交结果
GET    /status/{id}      # 查询状态
GET    /results          # 获取所有结果

# 系统管理
GET    /                 # 服务状态
GET    /health           # 健康检查
GET    /stats            # 系统统计
GET    /nodes            # 节点列表（计划）
数据格式规范
json
// 请求示例
{
  "code": "print('Hello')",
  "timeout": 300,
  "resources": {
    "cpu": 1.0,
    "memory": 512
  }
}

// 响应示例
{
  "task_id": 1,
  "status": "submitted",
  "message": "Task queued"
}
📊 扩展性设计
水平扩展支持
多调度中心: 通过共享存储（Redis）支持多实例

负载均衡: 节点可以连接任意调度中心

服务发现: 简单的节点注册和发现机制

存储扩展
python
# 存储接口抽象
class StorageBackend:
    def save_task(self, task): pass
    def get_task(self, task_id): pass
    def get_pending_tasks(self): pass
    def save_result(self, task_id, result): pass

# 支持多种后端
backends = {
    "memory": MemoryStorage,
    "redis": RedisStorage,
    "database": DatabaseStorage
}
插件系统（计划）
text
plugins/
├── detectors/          # 闲置检测插件
├── schedulers/         # 调度算法插件
├── executors/         # 执行引擎插件
└── monitors/          # 监控插件
🚀 部署架构
单机部署
text
单台计算机运行所有组件
┌─────────────────────────────────────┐
│          单台计算机                 │
│  ┌──────┐  ┌────────┐  ┌──────┐   │
│  │节点  │  │调度中心│  │Web界面│   │
│  └──────┘  └────────┘  └──────┘   │
└─────────────────────────────────────┘
局域网部署
text
多台计算机协作
┌────────────┐    ┌────────────┐    ┌────────────┐
│  调度中心   │◄──►│  节点1     │    │  节点2     │
│  + Web界面  │    │（Windows） │    │（macOS）   │
└────────────┘    └────────────┘    └────────────┘
云部署（未来）
text
云服务器 + 边缘设备
┌────────────┐    ┌────────────┐    ┌────────────┐
│  云调度中心  │◄──►│  办公电脑  │◄──►│  家庭电脑  │
│（AWS/Azure）│    │（节点）    │    │（节点）    │
└────────────┘    └────────────┘    └────────────┘
🔧 技术选型说明
编程语言: Python
选择理由:

丰富的科学计算库

跨平台支持良好

快速原型开发能力

广泛的社区支持

Web框架: FastAPI
选择理由:

高性能异步支持

自动API文档生成

类型提示和验证

现代Python框架

前端: Streamlit
选择理由:

无需前端开发经验

快速构建数据应用

与Python生态紧密集成

适合原型和演示

进程管理: 标准库subprocess
选择理由:

无需额外依赖

跨平台支持

细粒度控制

成熟稳定

📈 性能考虑
优化策略
懒加载: 平台模块按需加载

连接池: HTTP连接复用

缓存: 频繁访问数据缓存

批处理: 节点批量获取任务

性能指标
任务吞吐量: 每分钟处理任务数

响应时间: API平均响应时间

资源利用率: CPU/内存使用率

节点可用性: 平均在线时间比例

监控指标
yaml
monitoring:
  metrics:
    - tasks_queue_size
    - active_nodes_count
    - tasks_completed_per_minute
    - average_execution_time
    - error_rate
🔮 未来发展
短期规划 (v1.x)
完善Windows/macOS闲置检测

实现公平调度算法

添加基础监控和日志

优化错误处理和用户体验

中期规划 (v2.0)
支持GPU计算任务

实现去中心化调度

添加用户认证和计费

支持更多编程语言

长期愿景
构建算力共享网络

支持科学计算和AI训练

建立贡献者奖励机制

推动绿色计算发展

# API 参考文档

## 🏁 快速参考

| 组件 | 基础URL | 主要用途 |
|------|---------|----------|
| 调度中心 | `http://localhost:8000` | 任务分发、节点管理 |
| 网页界面 | `http://localhost:8501` | 用户交互、状态展示 |
| 节点客户端 | 内部通信 | 任务执行、心跳报告 |

## 🔧 调度中心API

### 基础端点

#### `GET /`
**描述**: 服务健康检查  
**响应**:
```json
{
  "service": "闲置计算调度中心",
  "status": "running",
  "version": "1.0.0",
  "queue_size": 3,
  "idle_nodes": 2
}
GET /health  描述: 详细健康状态
响应: json 复制   下载    {
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "components": {
    "task_queue": "healthy",
    "node_tracker": "healthy",
    "result_store": "healthy"
  }
}
任务管理
POST /tasks
描述: 提交新计算任务
请求:

json
{
  "code": "print(1+1)",
  "timeout": 300,
  "resources": {
    "cpu": 1.0,
    "memory": 512
  }
}
响应:

json
{
  "task_id": "task_001",
  "status": "queued",
  "estimated_wait": 30
}
GET /tasks/{task_id}
描述: 查询任务状态
响应:

json
{
  "task_id": "task_001",
  "status": "completed",
  "result": "2",
  "created_at": "2024-01-01T00:00:00Z",
  "completed_at": "2024-01-01T00:00:30Z",
  "executed_on": "node_macbook_001"
}
GET /tasks
描述: 查看所有任务
查询参数: ?status=pending (可选)
响应:

json
{
  "tasks": [
    {
      "task_id": "task_001",
      "status": "completed",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1
}
节点管理
GET /nodes
描述: 查看所有注册节点
响应:

json
{
  "nodes": [
    {
      "node_id": "node_macbook_001",
      "status": "idle",
      "resources": {
        "cpu_cores": 8,
        "memory_mb": 16384
      },
      "last_heartbeat": "2024-01-01T00:00:00Z"
    }
  ],
  "total_idle": 1,
  "total_nodes": 1
}
GET /nodes/{node_id}
描述: 查看节点详情
响应:

json
{
  "node_id": "node_macbook_001",
  "status": "idle",
  "platform": "macOS",
  "idle_since": "2024-01-01T00:00:00Z",
  "completed_tasks": 5,
  "total_compute_time": 150
}
🖥️ 网页界面API
网页端点
GET /web
描述: 主控制台页面（HTML）
内容: 任务提交表单 + 实时监控面板

GET /web/submit
描述: 任务提交页面
表单字段:

code (textarea, 必需): Python代码

timeout (number, 可选): 超时时间，默认300秒

cpu (number, 可选): CPU需求，默认1.0

memory (number, 可选): 内存需求(MB)，默认512

GET /web/monitor
描述: 实时监控面板
内容: 节点状态、任务队列、系统负载可视化

WebSocket实时更新
GET /ws/updates
描述: WebSocket连接获取实时事件
消息格式:

json
{
  "event": "task_updated",
  "data": {
    "task_id": "task_001",
    "status": "running",
    "node_id": "node_macbook_001"
  }
}
事件类型:

node_joined: 新节点加入

node_left: 节点离线

task_created: 新任务创建

task_started: 任务开始执行

task_completed: 任务完成

task_failed: 任务失败


描述: 节点定期报告状态
请求:

json
{
  "node_id": "node_macbook_001",
  "status": "idle",
  "resources": {
    "cpu_cores": 8,
    "memory_mb": 16384
  },
  "current_load": {
    "cpu_percent": 15.5,
    "memory_percent": 45.2
  }
}
响应:

json
{
  "status": "ok",
  "timestamp": "2024-01-01T00:00:00Z"
}
任务获取与提交
GET /internal/task/request
描述: 节点请求任务（闲置时调用）
响应:

json
{
  "has_task": true,
  "task": {
    "task_id": "task_001",
    "code": "print(1+1)",
    "timeout": 300
  }
}
或（无任务时）:

json
{
  "has_task": false,
  "wait_time": 30
}
POST /internal/task/result
描述: 节点提交任务结果
请求:

json
{
  "task_id": "task_001",
  "status": "success",
  "result": "2",
  "execution_time": 1.5,
  "error_message": null
}
📊 监控统计API
GET /stats
描述: 系统统计信息
响应:

json
{
  "time_period": "last_hour",
  "tasks": {
    "total": 100,
    "completed": 95,
    "failed": 5,
    "avg_time": 45.2
  },
  "nodes": {
    "total": 10,
    "idle": 3,
    "busy": 5,
    "offline": 2
  },
  "throughput": {
    "tasks_per_hour": 100,
    "compute_hours": 125.5
  }
}
GET /stats/nodes/top
描述: 贡献度最高的节点
查询参数: ?limit=10 (默认5)
响应:

markdown
## 📊 监控统计API

#### `GET /stats`
**描述**: 系统统计信息  
**响应**:
```json
{
  "time_period": "last_hour",
  "tasks": {
    "total": 100,
    "completed": 95,
    "failed": 5,
    "avg_time": 45.2
  },
  "nodes": {
    "total": 10,
    "idle": 3,
    "busy": 5,
    "offline": 2
  },
  "throughput": {
    "tasks_per_hour": 100,
    "compute_hours": 125.5
  }
}
GET /stats/nodes/queue
描述: 节点排队状态（公平调度）
查询参数: ?limit=20 (默认显示前20个)
响应:

json
{
  "scheduling_policy": "fair_queue_with_priority",
  "total_nodes_in_queue": 10,
  "nodes": [
    {
      "node_id": "node_new_001",
      "status": "idle",
      "waiting_since": "2024-01-01T00:00:00Z",
      "wait_time_seconds": 300,
      "priority": "high",  // 新节点或等待时间长的节点优先级高
      "completed_tasks": 0,
      "reason": "new_node_priority"
    },
    {
      "node_id": "node_mid_001",
      "status": "idle",
      "waiting_since": "2024-01-01T00:04:00Z",
      "wait_time_seconds": 60,
      "priority": "medium",
      "completed_tasks": 15,
      "reason": "fair_rotation"
    },
    {
      "node_id": "node_high_001",
      "status": "idle",
      "waiting_since": "2024-01-01T00:04:30Z",
      "wait_time_seconds": 30,
      "priority": "low",
      "completed_tasks": 50,
      "reason": "recently_served"
    }
  ]
}
⚖️ 公平调度算法说明
在 docs/DESIGN_DECISIONS.md 中添加：

公平调度策略
为了平衡 贡献奖励 和 新人机会，我们采用混合调度算法：

python
def calculate_node_priority(node):
    """计算节点优先级分数（分数越低优先级越高）"""
    
    # 基础等待时间（等待越久优先级越高）
    wait_score = -node.waiting_time_seconds
    
    # 贡献度奖励（但有限制）
    contribution_bonus = min(node.completed_tasks * 0.1, 10)  # 最多+10分
    
    # 新人加成（前10个任务有额外加成）
    newcomer_bonus = 0
    if node.completed_tasks < 10:
        newcomer_bonus = 20 - node.completed_tasks * 2
    
    # 最终优先级分数
    priority_score = wait_score + contribution_bonus + newcomer_bonus
    
    return priority_score

# 调度时选择优先级分数最低的节点
def select_next_node(available_nodes):
    return min(available_nodes, key=calculate_node_priority)
算法特点：

等待时间为主：等待时间占60%权重

贡献度有限奖励：完成任务可获奖励，但上限10分

新人保护：新节点前10个任务有额外加成

防饥饿机制：等待超过5分钟的节点自动升为最高优先级

优先级规则：

高优先级：等待>5分钟 或 新节点（任务数<5）

中优先级：等待1-5分钟 且 有一定贡献

低优先级：最近刚执行过任务（30分钟内）

这样既奖励了贡献者，又保证了新节点有机会，避免了"马太效应"。
⚠️ 错误处理
错误响应格式
json
{
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "任务不存在",
    "details": "任务ID: task_999 不存在于系统中"
  }
}
常见错误码
错误码	HTTP状态	说明
INVALID_REQUEST	400	请求参数无效
TASK_NOT_FOUND	404	任务不存在
NODE_NOT_FOUND	404	节点不存在
TASK_TIMEOUT	408	任务执行超时
RESOURCE_UNAVAILABLE	503	无可用计算资源
INTERNAL_ERROR	500	服务器内部错误
🔐 安全说明
当前实现
开发阶段：无认证，仅限本地网络访问

生产部署：建议配置防火墙、启用HTTPS

安全建议
网络隔离：调度中心部署在内网，通过反向代理对外

访问控制：基于IP白名单或API密钥

数据加密：启用HTTPS传输加密

输入验证：对任务代码进行基本安全检查

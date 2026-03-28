# API 参考文档

本文档描述 Idle-Sense 调度中心提供的 REST API 接口。

## 目录

- [基础信息](#基础信息)
- [认证](#认证)
- [任务管理](#任务管理)
- [节点管理](#节点管理)
- [系统状态](#系统状态)
- [错误处理](#错误处理)

---

## 基础信息

### 基础URL

```
http://localhost:8000
```

### 请求格式

- Content-Type: `application/json`
- 字符编码: `UTF-8`

### 响应格式

所有响应均为 JSON 格式：

```json
{
  "success": true,
  "data": { ... },
  "message": "操作成功"
}
```

错误响应：

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述"
  }
}
```

---

## 认证

### 用户注册

**POST** `/api/auth/register`

注册新用户账户。

**请求体**:
```json
{
  "username": "string",
  "password": "string",
  "email": "string (可选)"
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "user_id": "string",
    "username": "string"
  },
  "message": "注册成功"
}
```

### 用户登录

**POST** `/api/auth/login`

用户登录获取会话令牌。

**请求体**:
```json
{
  "username": "string",
  "password": "string"
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "token": "string",
    "user_id": "string",
    "username": "string"
  },
  "message": "登录成功"
}
```

### 用户登出

**POST** `/api/auth/logout`

用户登出，失效会话令牌。

**请求头**:
```
Authorization: Bearer <token>
```

**响应**:
```json
{
  "success": true,
  "message": "登出成功"
}
```

---

## 任务管理

### 提交任务

**POST** `/api/tasks/submit`

提交新的计算任务。

**请求体**:
```json
{
  "code": "string",
  "timeout": 300,
  "resources": {
    "cpu": 1.0,
    "memory": 512
  }
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | Python代码 |
| timeout | int | 否 | 超时时间（秒），默认300 |
| resources.cpu | float | 否 | CPU核心数限制 |
| resources.memory | int | 否 | 内存限制（MB） |

**响应**:
```json
{
  "success": true,
  "data": {
    "task_id": "uuid-string",
    "status": "pending",
    "created_at": "2024-01-01T00:00:00Z"
  },
  "message": "任务已提交"
}
```

### 查询任务状态

**GET** `/api/tasks/{task_id}`

查询指定任务的状态和结果。

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| task_id | string | 任务ID |

**响应**:
```json
{
  "success": true,
  "data": {
    "task_id": "uuid-string",
    "status": "completed",
    "created_at": "2024-01-01T00:00:00Z",
    "started_at": "2024-01-01T00:00:05Z",
    "completed_at": "2024-01-01T00:00:10Z",
    "result": "任务执行结果",
    "node_id": "node-001",
    "execution_time": 5.2
  }
}
```

**任务状态**:

| 状态 | 说明 |
|------|------|
| pending | 等待执行 |
| running | 正在执行 |
| completed | 执行完成 |
| failed | 执行失败 |
| cancelled | 已取消 |
| timeout | 执行超时 |

### 列出任务

**GET** `/api/tasks`

列出所有任务或筛选特定条件的任务。

**查询参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| status | string | 按状态筛选 |
| user_id | string | 按用户筛选 |
| limit | int | 返回数量限制 |
| offset | int | 偏移量（分页） |

**响应**:
```json
{
  "success": true,
  "data": {
    "tasks": [
      {
        "task_id": "uuid-string",
        "status": "completed",
        "created_at": "2024-01-01T00:00:00Z"
      }
    ],
    "total": 100,
    "limit": 20,
    "offset": 0
  }
}
```

### 取消任务

**POST** `/api/tasks/{task_id}/cancel`

取消正在等待或执行中的任务。

**响应**:
```json
{
  "success": true,
  "message": "任务已取消"
}
```

### 删除任务

**DELETE** `/api/tasks/{task_id}`

删除已完成的任务记录。

**响应**:
```json
{
  "success": true,
  "message": "任务已删除"
}
```

---

## 节点管理

### 节点注册

**POST** `/api/nodes/register`

计算节点向调度中心注册。

**请求体**:
```json
{
  "node_id": "string",
  "node_name": "string",
  "resources": {
    "cpu_cores": 8,
    "memory_mb": 16384,
    "platform": "Windows"
  }
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "node_id": "string",
    "registered_at": "2024-01-01T00:00:00Z"
  },
  "message": "节点注册成功"
}
```

### 节点心跳

**POST** `/api/nodes/{node_id}/heartbeat`

节点发送心跳保持在线状态。

**请求体**:
```json
{
  "status": "idle",
  "resources": {
    "cpu_usage": 15.5,
    "memory_usage": 45.2
  },
  "idle_since": "2024-01-01T00:05:00Z"
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "task": null
  }
}
```

如果有待分配的任务：

```json
{
  "success": true,
  "data": {
    "task": {
      "task_id": "uuid-string",
      "code": "print('hello')",
      "timeout": 300
    }
  }
}
```

### 列出节点

**GET** `/api/nodes`

列出所有注册的节点。

**查询参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| status | string | 按状态筛选 (idle/busy/offline) |
| limit | int | 返回数量限制 |

**响应**:
```json
{
  "success": true,
  "data": {
    "nodes": [
      {
        "node_id": "node-001",
        "node_name": "MacBook-Pro",
        "status": "idle",
        "resources": {
          "cpu_cores": 8,
          "memory_mb": 16384
        },
        "tasks_completed": 50,
        "last_heartbeat": "2024-01-01T00:00:00Z"
      }
    ],
    "total": 10
  }
}
```

### 节点详情

**GET** `/api/nodes/{node_id}`

获取指定节点的详细信息。

**响应**:
```json
{
  "success": true,
  "data": {
    "node_id": "node-001",
    "node_name": "MacBook-Pro",
    "status": "idle",
    "resources": {
      "cpu_cores": 8,
      "memory_mb": 16384,
      "platform": "macOS"
    },
    "statistics": {
      "tasks_completed": 50,
      "total_compute_time": 3600,
      "contribution_score": 85.5
    },
    "registered_at": "2024-01-01T00:00:00Z",
    "last_heartbeat": "2024-01-01T00:05:00Z"
  }
}
```

### 节点下线

**POST** `/api/nodes/{node_id}/offline`

节点主动下线。

**响应**:
```json
{
  "success": true,
  "message": "节点已下线"
}
```

---

## 系统状态

### 健康检查

**GET** `/health`

检查调度中心健康状态。

**响应**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 86400
}
```

### 系统统计

**GET** `/api/stats`

获取系统整体统计信息。

**响应**:
```json
{
  "success": true,
  "data": {
    "nodes": {
      "total": 10,
      "idle": 5,
      "busy": 3,
      "offline": 2
    },
    "tasks": {
      "total": 1000,
      "pending": 50,
      "running": 10,
      "completed": 900,
      "failed": 40
    },
    "compute": {
      "total_hours": 100,
      "tasks_per_hour": 10
    }
  }
}
```

### 调度器状态

**GET** `/api/scheduler/status`

获取调度器详细状态。

**响应**:
```json
{
  "success": true,
  "data": {
    "status": "running",
    "queue_size": 50,
    "active_nodes": 8,
    "config": {
      "max_queue_size": 1000,
      "scheduling_policy": "fair_priority"
    }
  }
}
```

---

## 错误处理

### 错误代码

| 代码 | HTTP状态码 | 说明 |
|------|-----------|------|
| INVALID_REQUEST | 400 | 请求参数无效 |
| UNAUTHORIZED | 401 | 未授权访问 |
| FORBIDDEN | 403 | 权限不足 |
| NOT_FOUND | 404 | 资源不存在 |
| CONFLICT | 409 | 资源冲突 |
| INTERNAL_ERROR | 500 | 服务器内部错误 |
| SERVICE_UNAVAILABLE | 503 | 服务暂时不可用 |

### 错误响应示例

```json
{
  "success": false,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "代码不能为空",
    "details": {
      "field": "code",
      "constraint": "required"
    }
  }
}
```

---

## 速率限制

API 请求受以下速率限制：

| 端点类型 | 限制 |
|---------|------|
| 任务提交 | 100次/分钟 |
| 状态查询 | 1000次/分钟 |
| 其他操作 | 500次/分钟 |

超出限制时返回：

```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "请求过于频繁，请稍后重试"
  }
}
```

---

## WebSocket 接口

### 连接

```
ws://localhost:8000/ws
```

### 消息格式

**订阅任务状态**:
```json
{
  "action": "subscribe",
  "channel": "task_status",
  "task_id": "uuid-string"
}
```

**接收状态更新**:
```json
{
  "channel": "task_status",
  "data": {
    "task_id": "uuid-string",
    "status": "completed",
    "result": "执行结果"
  }
}
```

---

## SDK 示例

### Python

```python
import requests

# 提交任务
response = requests.post(
    "http://localhost:8000/api/tasks/submit",
    json={
        "code": "print('Hello, World!')",
        "timeout": 60
    }
)
task_id = response.json()["data"]["task_id"]

# 查询状态
status = requests.get(f"http://localhost:8000/api/tasks/{task_id}")
print(status.json())
```

### JavaScript

```javascript
// 提交任务
const response = await fetch('http://localhost:8000/api/tasks/submit', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    code: "print('Hello, World!')",
    timeout: 60
  })
});
const data = await response.json();
const taskId = data.data.task_id;

// 查询状态
const status = await fetch(`http://localhost:8000/api/tasks/${taskId}`);
console.log(await status.json());
```

---

**最后更新**: 2026-03-28

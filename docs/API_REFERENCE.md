# API 参考文档
## 📋 基础信息

### 服务器信息
- **基础URL**: `http://localhost:8000`（开发环境）
- **API版本**: v1（通过路径前缀）
- **数据格式**: JSON
- **认证**: 开发阶段无需认证

### 服务状态
GET http://localhost:8000/

text

**响应示例**:
```json
{
  "service": "Idle Computing Scheduler",
  "status": "running",
  "version": "1.0.0",
  "server_id": "a1b2c3d4",
  "task_count": 5,
  "pending_tasks": 2
}
🎯 任务管理 API
提交新任务
text
POST http://localhost:8000/submit
Content-Type: application/json
请求体:

json
{
  "code": "print('Hello World')",
  "timeout": 300,
  "resources": {
    "cpu": 1.0,
    "memory": 512
  }
}
参数说明:

code: 必需，要执行的Python代码

timeout: 可选，超时时间（秒），默认300

resources: 可选，资源需求，默认 {"cpu": 1.0, "memory": 512}

成功响应:

json
{
  "task_id": 1,
  "status": "submitted",
  "server_id": "a1b2c3d4",
  "message": "Task 1 has been queued"
}
获取待处理任务
text
GET http://localhost:8000/get_task
响应示例（有任务时）:

json
{
  "task_id": 1,
  "code": "print('Hello World')",
  "status": "assigned",
  "created_at": 1640995200.123,
  "message": "Task 1 assigned for execution"
}
响应示例（无任务时）:

json
{
  "task_id": null,
  "code": null,
  "status": "no_tasks",
  "message": "No pending tasks available"
}
提交任务结果
text
POST http://localhost:8000/submit_result
Content-Type: application/json
请求体:

json
{
  "task_id": 1,
  "result": "Hello World"
}
成功响应:

json
{
  "status": "ok",
  "task_id": 1,
  "message": "Result for task 1 recorded"
}
查询任务状态
text
GET http://localhost:8000/status/{task_id}
路径参数:

task_id: 任务ID（整数）

响应示例:

json
{
  "task_id": 1,
  "status": "completed",
  "result": "Hello World",
  "created_at": 1640995200.123,
  "completed_at": 1640995205.456
}
可能的状态值:

pending: 等待中

running: 执行中

completed: 已完成

failed: 失败

获取所有结果
text
GET http://localhost:8000/results
响应示例:

json
{
  "count": 3,
  "results": [
    {
      "task_id": 1,
      "result": "Hello World",
      "completed_at": 1640995205.456
    },
    {
      "task_id": 2,
      "result": "42",
      "completed_at": 1640995210.789
    }
  ],
  "server_id": "a1b2c3d4"
}
🖥️ 系统管理 API
健康检查
text
GET http://localhost:8000/health
响应示例:

json
{
  "status": "healthy",
  "timestamp": 1640995200.123,
  "server_id": "a1b2c3d4",
  "components": {
    "task_queue": "healthy",
    "memory_storage": "healthy"
  }
}
系统统计
text
GET http://localhost:8000/stats
响应示例:

json
{
  "time_period": "all_time",
  "tasks": {
    "total": 10,
    "completed": 7,
    "pending": 2,
    "failed": 1,
    "avg_time": 12.34
  },
  "nodes": {
    "total": 0,
    "idle": 0,
    "busy": 0,
    "offline": 0
  },
  "throughput": {
    "tasks_per_hour": 0,
    "compute_hours": 0
  }
}
🔌 客户端节点 API（内部使用）
节点心跳（计划功能）
text
POST http://localhost:8000/internal/heartbeat
Content-Type: application/json
请求体:

json
{
  "node_id": "node-001",
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
节点获取任务（计划功能）
text
GET http://localhost:8000/internal/task
节点提交结果（计划功能）
text
POST http://localhost:8000/internal/result
Content-Type: application/json
🌐 网页界面
网页控制台
text
GET http://localhost:8501
通过 Streamlit 提供的 Web 界面，包含：

任务提交表单

实时任务监控

节点状态显示

系统统计图表

⚠️ 错误处理
错误响应格式
json
{
  "detail": "错误描述信息"
}
常见 HTTP 状态码
状态码	含义	常见原因
200	成功	请求成功完成
400	错误请求	参数缺失或格式错误
404	未找到	任务或资源不存在
422	无法处理	数据验证失败
500	服务器错误	服务器内部错误
具体错误示例
任务不存在:

json
{
  "detail": "Task 999 not found"
}
代码过长:

json
{
  "detail": "Code too long (max 10000 characters)"
}
空代码:

json
{
  "detail": "Code cannot be empty"
}
🔐 安全说明
开发环境
无认证机制

CORS 允许所有来源 (*)

仅限本地网络访问

生产环境建议
启用认证: 添加 API 密钥或 OAuth

限制 CORS: 只允许可信域名

启用 HTTPS: 使用 SSL/TLS 加密

设置防火墙: 限制访问 IP

添加限流: 防止滥用

📡 WebSocket 支持（计划功能）
实时更新
text
WS ws://localhost:8000/ws/updates
消息类型:

json
{
  "event": "task_updated",
  "data": {
    "task_id": 1,
    "status": "running",
    "node_id": "node-001"
  }
}
支持的事件:

task_created: 新任务创建

task_started: 任务开始执行

task_completed: 任务完成

task_failed: 任务失败

node_joined: 新节点加入

node_left: 节点离线

📊 API 使用示例
Python 客户端示例
python
import requests

# 1. 提交任务
def submit_task(code, timeout=300):
    url = "http://localhost:8000/submit"
    payload = {
        "code": code,
        "timeout": timeout
    }
    response = requests.post(url, json=payload)
    return response.json()

# 2. 查询状态
def get_task_status(task_id):
    url = f"http://localhost:8000/status/{task_id}"
    response = requests.get(url)
    return response.json()

# 3. 获取系统状态
def get_system_stats():
    url = "http://localhost:8000/stats"
    response = requests.get(url)
    return response.json()

# 使用示例
if __name__ == "__main__":
    # 提交计算任务
    result = submit_task("print(1 + 1)")
    task_id = result["task_id"]
    print(f"任务提交成功，ID: {task_id}")
    
    # 等待并检查结果
    import time
    while True:
        status = get_task_status(task_id)
        if status["status"] == "completed":
            print(f"任务完成，结果: {status['result']}")
            break
        time.sleep(1)
cURL 示例
bash
# 1. 检查服务状态
curl http://localhost:8000/

# 2. 提交任务
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d '{"code": "print(\"Hello from cURL\")"}'

# 3. 查询任务状态
curl http://localhost:8000/status/1

# 4. 获取系统统计
curl http://localhost:8000/stats
📈 API 版本历史
v1.0.0 (当前)
基本任务提交和获取

任务状态查询

结果提交和查看

系统健康检查

基础统计信息

计划功能
RESTful API 端点 (/api/v1/)

节点注册和管理

高级调度算法

WebSocket 实时更新

用户认证和授权

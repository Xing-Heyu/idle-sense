markdown
# API 参考文档

## 📋 基础信息

### 服务器信息
- **基础URL**: `http://localhost:8000`（开发环境）
- **API版本**: v1.0.0
- **数据格式**: JSON
- **认证**: 开发阶段无需认证

### 服务状态端点

#### GET /
**描述**: 获取服务基本信息

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
POST /submit
描述: 提交新的计算任务

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

code: 必需，要执行的Python代码（字符串）

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
GET /get_task
描述: 获取一个待处理的任务

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
POST /submit_result
描述: 提交任务执行结果

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
GET /status/{task_id}
描述: 查询指定任务的状态

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
任务状态说明:

pending: 等待中

running: 执行中

completed: 已完成

failed: 失败

获取所有结果
GET /results
描述: 获取所有已完成任务的结果

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
GET /health
描述: 检查服务健康状况

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
GET /stats
描述: 获取系统统计信息

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
⚠️ 错误处理
错误响应格式
所有错误都返回以下格式：

json
{
  "detail": "错误描述信息"
}
HTTP 状态码对照表
状态码	含义	常见原因
200	成功	请求成功完成
400	错误请求	参数缺失或格式错误
404	未找到	任务或资源不存在
500	服务器错误	服务器内部错误
常见错误示例
任务不存在 (404):

json
{
  "detail": "Task 999 not found"
}
代码过长 (400):

json
{
  "detail": "Code too long (max 10000 characters)"
}
空代码 (400):

json
{
  "detail": "Code cannot be empty"
}
📡 使用示例
Python 客户端示例
python
import requests
import time

class IdleClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def submit_task(self, code, timeout=300):
        """提交任务"""
        payload = {
            "code": code,
            "timeout": timeout
        }
        response = requests.post(f"{self.base_url}/submit", json=payload)
        return response.json()
    
    def get_task_status(self, task_id):
        """获取任务状态"""
        response = requests.get(f"{self.base_url}/status/{task_id}")
        return response.json()
    
    def wait_for_completion(self, task_id, poll_interval=1):
        """等待任务完成"""
        while True:
            status = self.get_task_status(task_id)
            if status["status"] == "completed":
                return status["result"]
            elif status["status"] == "failed":
                raise Exception(f"Task failed: {status}")
            time.sleep(poll_interval)

# 使用示例
if __name__ == "__main__":
    client = IdleClient()
    
    # 提交任务
    result = client.submit_task("print(1 + 1)")
    task_id = result["task_id"]
    print(f"Task submitted: {task_id}")
    
    # 等待结果
    try:
        result = client.wait_for_completion(task_id)
        print(f"Task result: {result}")
    except Exception as e:
        print(f"Error: {e}")
cURL 示例
bash
# 检查服务状态
curl http://localhost:8000/

# 提交任务
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d '{"code": "print(1 + 1)"}'

# 查询任务状态
curl http://localhost:8000/status/1

# 获取系统统计
curl http://localhost:8000/stats
🔐 安全说明
开发环境配置
无认证机制

CORS 允许所有来源 (*)

仅限本地网络访问

生产环境建议
启用 HTTPS

配置 API 密钥认证

限制 CORS 域名

设置请求频率限制

启用请求日志

📊 API 版本历史
v1.0.0 (当前版本)
基本任务提交和获取

任务状态查询

结果提交和查看

系统健康检查

基础统计信息

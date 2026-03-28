# 快速入门指南

本指南帮助您在 5 分钟内启动并运行 Idle-Sense。

## 前提条件

- Python 3.9 或更高版本
- pip 包管理器
- Git 版本控制

## 第一步：获取代码

```bash
# 克隆仓库
git clone https://github.com/Xing-Heyu/idle-sense.git
cd idle-sense
```

## 第二步：安装依赖

```bash
# 安装所有依赖
pip install -r requirements.txt
```

## 第三步：启动服务

### 方式一：单机体验（推荐新手）

打开三个终端窗口：

**终端 1 - 调度中心**:
```bash
python -m legacy.scheduler.simple_server
```

**终端 2 - 计算节点**:
```bash
python -m legacy.node.simple_client --scheduler http://localhost:8000
```

**终端 3 - Web 界面**:
```bash
streamlit run src/presentation/streamlit/app.py
```

### 方式二：仅启动调度中心

```bash
python -m legacy.scheduler.simple_server
```

然后通过 API 提交任务：

```python
import requests

response = requests.post(
    "http://localhost:8000/api/tasks/submit",
    json={"code": "print('Hello, Idle-Sense!')"}
)
print(response.json())
```

## 第四步：验证运行

### 检查调度中心

```bash
curl http://localhost:8000/health
```

预期响应：
```json
{"status": "healthy", "version": "1.0.0"}
```

### 检查节点状态

```bash
curl http://localhost:8000/api/nodes
```

### 访问 Web 界面

打开浏览器访问：http://localhost:8501

## 第五步：提交第一个任务

### 通过 Web 界面

1. 打开 http://localhost:8501
2. 点击"注册"创建账户
3. 登录后进入"任务提交"页面
4. 输入代码并提交

### 通过 API

```python
import requests

# 提交任务
response = requests.post(
    "http://localhost:8000/api/tasks/submit",
    json={
        "code": """
# 计算斐波那契数列
def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)

result = fib(20)
print(f"斐波那契数列第20项: {result}")
__result__ = result
""",
        "timeout": 60
    }
)

task_id = response.json()["data"]["task_id"]
print(f"任务ID: {task_id}")

# 查询结果
import time
while True:
    status = requests.get(f"http://localhost:8000/api/tasks/{task_id}")
    data = status.json()["data"]
    print(f"状态: {data['status']}")
    if data["status"] in ["completed", "failed", "timeout"]:
        print(f"结果: {data.get('result')}")
        break
    time.sleep(2)
```

## 常见问题

### 端口被占用

如果 8000 端口被占用，可以指定其他端口：

```bash
python -m legacy.scheduler.simple_server --port 8080
```

### 节点无法连接

1. 确认调度中心已启动
2. 检查防火墙设置
3. 验证 URL 是否正确

### 闲置检测不工作

确保节点客户端正在运行，并且电脑处于闲置状态。

## 下一步

- 阅读 [用户指南](USER_GUIDE.md) 了解详细功能
- 查看 [API 参考](docs/API_REFERENCE.md) 了解接口详情
- 阅读 [架构文档](docs/ARCHITECTURE.md) 了解系统设计

---

**祝您使用愉快！** 🎉

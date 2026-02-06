```markdown
# 快速开始指南

## 🚀 5分钟快速体验

### 前提条件
- Python 3.8 或更高版本
- pip 包管理器
- 网络连接（用于下载依赖）

### 步骤1：获取代码
```bash
# 克隆仓库（如果使用Git）
git clone https://github.com/yourname/idle-accelerator
cd idle-accelerator

# 或者直接下载并解压
步骤2：安装依赖
bash
# 安装所需Python包
pip install -r requirements.txt
步骤3：启动调度中心
bash
# 在终端1中运行
python scheduler/simple_server.py
你应该看到类似输出：

text
[Scheduler] Starting server on http://localhost:8000
[Scheduler] Server ID: a1b2c3d4
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
步骤4：启动计算节点
bash
# 在终端2中运行
python node/simple_client.py --scheduler http://localhost:8000
你应该看到类似输出：

text
Idle Computing Node Client
============================================================
Platform: Windows
Idle sense: Available
Scheduler: http://localhost:8000
Check interval: 30s
------------------------------------------------------------
[00:00:00] Checking system idle status...
步骤5：测试任务提交
bash
# 在终端3中运行（或使用Python交互模式）
python -c "
import requests

# 提交一个简单任务
response = requests.post('http://localhost:8000/submit', 
    json={'code': 'print(1 + 1)'})
    
task_id = response.json()['task_id']
print(f'Task submitted: {task_id}')

# 等待并获取结果
import time
while True:
    status = requests.get(f'http://localhost:8000/status/{task_id}').json()
    if status['status'] == 'completed':
        print(f'Result: {status[\"result\"]}')
        break
    time.sleep(1)
"
步骤6：查看网页界面（可选）
bash
# 在终端4中运行
streamlit run web_interface.py
然后在浏览器中打开：http://localhost:8501

🎯 完整功能演示
演示1：单机完整流程
bash
# 运行单机演示脚本
python demo/demo_single_machine.py
这个演示会自动：

启动调度中心

启动计算节点

提交计算任务

监控执行过程

显示最终结果

演示2：网页界面体验
bash
# 运行网页界面演示
python demo/demo_web_interface.py
这个演示会：

自动启动所有服务

打开浏览器界面

提交示例任务

展示网页功能

演示3：分布式计算（多机）
bash
# 运行局域网演示
python demo/demo_local_network.py
按照提示在其他电脑上启动节点，体验分布式计算。

📁 项目结构概览
text
idle-accelerator/
├── idle_sense/          # 闲置检测库
│   ├── core.py         # 跨平台接口
│   ├── windows.py      # Windows实现
│   ├── macos.py        # macOS实现
│   └── __init__.py     # 包定义
├── scheduler/          # 调度中心
│   └── simple_server.py # FastAPI服务器
├── node/              # 计算节点
│   └── simple_client.py # 节点客户端
├── web_interface.py    # 网页控制台
├── examples/          # 示例任务
├── demo/             # 演示脚本
├── docs/             # 文档
├── config/           # 配置文件
└── scripts/          # 部署脚本
🔧 基本配置
环境变量配置
bash
# 调度中心配置
export SCHEDULER_HOST=0.0.0.0
export SCHEDULER_PORT=8000

# 节点配置
export SCHEDULER_URL=http://localhost:8000
export NODE_NAME=my-computer

# 网页界面配置
export STREAMLIT_PORT=8501
配置文件
复制并修改配置文件：

bash
cp config/config.yaml.example config/config.yaml
cp .env.example .env
编辑 config/config.yaml 调整设置。

📊 验证安装
运行验证脚本检查所有组件：

bash
python scripts/quick_test.py
如果一切正常，你应该看到：

text
⚡ 闲置计算加速器 - 全面测试
============================================================
步骤 1: 测试调度中心连接
✅ 连接成功!
   服务: Idle Computing Scheduler
   状态: running
   版本: 1.0.0

步骤 2: 测试闲置检测库
✅ 平台检测: Windows
✅ 模块健康: True - Platform module for Windows loaded successfully
...

🎉 所有测试通过！系统运行正常。
🚨 故障排除
常见问题1：端口占用
text
错误: [Errno 48] Address already in use
解决方法：

bash
# 查找占用端口的进程
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# 停止占用进程或更改端口
python scheduler/simple_server.py --port 8001
常见问题2：依赖安装失败
text
错误: No module named 'fastapi'
解决方法：

bash
# 确保使用正确的pip
python -m pip install -r requirements.txt

# 或手动安装核心依赖
pip install fastapi uvicorn psutil requests streamlit
常见问题3：节点无法连接
text
错误: Connection refused
解决方法：

确保调度中心正在运行

检查防火墙设置

验证URL是否正确

bash
# 测试连接
curl http://localhost:8000/
常见问题4：权限问题
text
错误: Permission denied
解决方法：

bash
# 使用虚拟环境
python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
pip install -r requirements.txt
📈 下一步
学习更多
阅读设计文档: docs/DESIGN_DECISIONS.md

查看API文档: docs/API_REFERENCE.md

研究架构: docs/ARCHITECTURE.md

尝试示例
bash
# 运行数学计算示例
python examples/math_computation.py

# 运行数据处理示例
python examples/data_processing.py

# 运行性能测试
python examples/benchmark.py
部署到生产
使用Docker部署: scripts/deploy_demo.sh

配置系统服务: 参考 scripts/setup_scheduler.sh

设置监控: 启用统计端点

🤝 获取帮助
查看完整文档: 访问 docs/ 目录

运行演示脚本: demo/ 目录中的各种演示

查看示例代码: examples/ 目录中的任务示例

报告问题: 在GitHub仓库创建Issue

恭喜！ 你已经成功启动并运行了闲置计算加速器。现在可以开始提交计算任务，或继续探索高级功能。

开始你的第一个分布式计算任务吧！ 🎉

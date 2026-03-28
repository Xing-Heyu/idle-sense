# 用户指南

## 目录

1. [系统要求](#系统要求)
2. [安装指南](#安装指南)
3. [快速开始](#快速开始)
4. [核心概念](#核心概念)
5. [使用流程](#使用流程)
6. [Web界面使用](#web界面使用)
7. [命令行使用](#命令行使用)
8. [配置说明](#配置说明)
9. [常见问题](#常见问题)

---

## 系统要求

### 操作系统

- **Windows**: Windows 10/11
- **macOS**: macOS 10.15 (Catalina) 或更高
- **Linux**: Ubuntu 18.04+, Debian 10+, CentOS 8+

### 软件依赖

- **Python**: 3.9 或更高版本
- **pip**: 最新版本
- **Git**: 用于克隆仓库

### 硬件要求

- **CPU**: 双核及以上
- **内存**: 4GB RAM 最小，8GB 推荐
- **磁盘**: 1GB 可用空间
- **网络**: 稳定的互联网连接

---

## 安装指南

### 1. 检查Python版本

```bash
python --version
# 应显示 Python 3.9.x 或更高
```

### 2. 克隆项目

```bash
git clone https://github.com/Xing-Heyu/idle-sense.git
cd idle-sense
```

### 3. 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

### 5. 验证安装

```bash
python -c "import legacy; print('安装成功!')"
```

---

## 快速开始

### 场景一：单机体验

在一台电脑上体验完整功能：

```bash
# 终端1: 启动调度中心
python -m legacy.scheduler.simple_server

# 终端2: 启动计算节点
python -m legacy.node.simple_client --scheduler http://localhost:8000

# 终端3: 启动Web界面
streamlit run src/presentation/streamlit/app.py
```

访问 http://localhost:8501 打开Web界面。

### 场景二：局域网部署

在局域网内多台电脑协作：

**服务器电脑（调度中心）**:
```bash
python -m legacy.scheduler.simple_server --host 0.0.0.0
```

**其他电脑（计算节点）**:
```bash
python -m legacy.node.simple_client --scheduler http://服务器IP:8000
```

---

## 核心概念

### 调度中心 (Scheduler)

调度中心是整个系统的核心，负责：
- 管理任务队列
- 分配任务给计算节点
- 跟踪任务状态和结果
- 维护节点注册信息

### 计算节点 (Node)

计算节点是执行任务的客户端，负责：
- 检测本机闲置状态
- 向调度中心注册和心跳
- 接收并执行任务
- 返回执行结果

### 任务 (Task)

任务是待执行的计算单元，包含：
- Python代码
- 执行超时设置
- 资源需求

### 闲置检测 (Idle Detection)

系统通过多维度检测判断电脑是否闲置：
- 用户无操作时间
- CPU使用率
- 内存使用率
- 屏幕锁定状态

---

## 使用流程

### 作为任务提交者

1. **注册账户**
   - 打开Web界面
   - 点击"注册"
   - 填写用户名和密码

2. **提交任务**
   - 登录后进入"任务提交"页面
   - 输入Python代码
   - 设置超时时间
   - 点击提交

3. **监控任务**
   - 在"任务监控"页面查看状态
   - 等待任务完成
   - 查看执行结果

### 作为算力提供者

1. **启动节点**
   ```bash
   python -m legacy.node.simple_client --scheduler http://调度中心地址:8000
   ```

2. **保持运行**
   - 节点会自动检测闲置状态
   - 闲置时自动接收任务
   - 执行完成后自动上报结果

3. **查看贡献**
   - 在Web界面查看贡献统计
   - 查看获得的代币奖励

---

## Web界面使用

### 登录/注册页面

- 新用户注册账户
- 已有用户登录系统

### 任务提交页面

- 代码编辑器
- 超时设置
- 资源限制配置
- 示例代码选择

### 任务监控页面

- 任务列表
- 实时状态更新
- 结果查看
- 任务取消

### 节点管理页面

- 节点列表
- 节点状态
- 资源使用情况
- 节点控制

### 系统统计页面

- 整体统计
- 任务趋势
- 节点活跃度
- 资源利用率

---

## 命令行使用

### 调度中心命令

```bash
# 启动调度中心
python -m legacy.scheduler.simple_server

# 指定端口
python -m legacy.scheduler.simple_server --port 8080

# 指定监听地址
python -m legacy.scheduler.simple_server --host 0.0.0.0

# 检查状态
python -m legacy.scheduler.cli status
```

### 节点命令

```bash
# 启动节点
python -m legacy.node.simple_client --scheduler http://localhost:8000

# 指定节点名称
python -m legacy.node.simple_client --scheduler http://localhost:8000 --name my-node

# 列出节点
python -m legacy.node.cli list
```

### 任务命令

```bash
# 提交任务
python -m legacy.task.cli submit --code "print('Hello')"

# 从文件提交
python -m legacy.task.cli submit --file task.py

# 查询状态
python -m legacy.task.cli status --task-id <TASK_ID>

# 列出任务
python -m legacy.task.cli list
```

---

## 配置说明

### 配置文件位置

- 主配置: `config/config.yaml`
- 环境变量: `.env`

### 调度中心配置

```yaml
scheduler:
  host: "0.0.0.0"
  port: 8000
  log_level: "INFO"
  
  tasks:
    max_queue_size: 1000
    result_ttl: 3600
```

### 节点配置

```yaml
node:
  scheduler_url: "http://localhost:8000"
  node_name: "my-node"
  
  idle_detection:
    check_interval: 30
    idle_threshold: 300
    cpu_threshold: 30.0
    memory_threshold: 70.0
```

### 安全配置

```yaml
security:
  max_task_time: 300
  max_memory_mb: 1024
  network_access: false
  auto_cleanup: true
```

---

## 常见问题

### Q: 节点无法连接调度中心？

**A**: 检查以下几点：
1. 调度中心是否已启动
2. 网络连接是否正常
3. 防火墙是否放行端口
4. 调度器URL是否正确

### Q: 任务一直处于等待状态？

**A**: 可能原因：
1. 没有可用的计算节点
2. 所有节点都在忙碌
3. 任务资源需求过高

### Q: 闲置检测不准确？

**A**: 调整配置：
1. 降低 `idle_threshold` 阈值
2. 调整 CPU/内存阈值
3. 检查屏幕锁定检测

### Q: 如何查看日志？

**A**: 日志位置：
- 调度中心: `logs/scheduler.log`
- 节点: `logs/node.log`
- Web界面: `logs/web.log`

### Q: 如何重置系统？

**A**: 
```bash
# 停止所有服务
# 删除数据目录
rm -rf data/
# 重新启动
```

---

## 获取帮助

- **文档**: [docs/](docs/)
- **问题反馈**: [GitHub Issues](https://github.com/Xing-Heyu/idle-sense/issues)
- **API参考**: [docs/API_REFERENCE.md](docs/API_REFERENCE.md)

---

**最后更新**: 2026-03-28

markdown
# 部署指南

## 🚀 快速开始

### 开发环境（单机测试）
```bash
# 1. 克隆项目
git clone https://github.com/yourname/idle-accelerator
cd idle-accelerator

# 2. 安装Python依赖
pip install -r requirements.txt

# 3. 启动调度中心（终端1）
python scheduler/simple_server.py
# 输出：Server running at http://localhost:8000

# 4. 启动计算节点（终端2）
python node/simple_client.py --scheduler http://localhost:8000
# 输出：Node started, checking idle status...

# 5. 启动网页界面（终端3，可选）
streamlit run web_interface.py
# 输出：Web interface at http://localhost:8501
局域网部署（多台电脑）
bash
# 在调度中心电脑上（IP: 192.168.1.100）
python scheduler/simple_server.py --host 0.0.0.0 --port 8000

# 在各节点电脑上
python node/simple_client.py \
  --scheduler http://192.168.1.100:8000 \
  --node-name "macbook-office" \
  --check-interval 30
🐳 Docker 部署
1. 调度中心Docker镜像
dockerfile
# Dockerfile.scheduler
FROM python:3.11-slim

WORKDIR /app

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY scheduler/ ./scheduler/
COPY idle_sense/ ./idle_sense/

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "scheduler.simple_server:app", "--host", "0.0.0.0", "--port", "8000"]
构建并运行：

bash
docker build -f Dockerfile.scheduler -t idle-scheduler .
docker run -p 8000:8000 --name scheduler idle-scheduler
2. 节点客户端Docker镜像
dockerfile
# Dockerfile.node
FROM python:3.11-slim

WORKDIR /app

# 安装系统工具（用于闲置检测）
RUN apt-get update && apt-get install -y \
    procps \      # ps命令
    lsof \        # 检查进程
    htop \        # 资源监控
    && rm -rf /var/lib/apt/lists/*

# Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY node/ ./node/
COPY idle_sense/ ./idle_sense/

# 启动节点
CMD ["python", "node/simple_client.py", "--scheduler", "http://scheduler:8000"]
3. Docker Compose一键部署
yaml
# docker-compose.yml
version: '3.8'

services:
  # Redis缓存（可选，用于生产环境）
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # 调度中心
  scheduler:
    build:
      context: .
      dockerfile: Dockerfile.scheduler
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
    restart: unless-stopped

  # 计算节点（可根据需要启动多个）
  node1:
    build:
      context: .
      dockerfile: Dockerfile.node
    environment:
      - NODE_NAME=node-1
      - SCHEDULER_URL=http://scheduler:8000
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
    depends_on:
      - scheduler
    restart: unless-stopped

  node2:
    build:
      context: .
      dockerfile: Dockerfile.node
    environment:
      - NODE_NAME=node-2
      - SCHEDULER_URL=http://scheduler:8000
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
    depends_on:
      - scheduler
    restart: unless-stopped

  # 网页界面（Streamlit）
  web:
    build:
      context: .
      dockerfile: Dockerfile.scheduler  # 复用相同基础
    command: streamlit run web_interface.py --server.port 8501 --server.address 0.0.0.0
    ports:
      - "8501:8501"
    depends_on:
      - scheduler
    restart: unless-stopped

volumes:
  redis_data:
启动集群：

bash
docker-compose up -d
docker-compose ps  # 查看服务状态
☁️ 云服务器部署
方案A：单服务器部署（推荐初学者）
bash
# 在云服务器上（Ubuntu 22.04）
# 1. 连接服务器
ssh user@your-server-ip

# 2. 安装基础软件
sudo apt update
sudo apt install -y python3-pip python3-venv git nginx

# 3. 克隆项目
git clone https://github.com/yourname/idle-accelerator.git
cd idle-accelerator

# 4. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 5. 安装依赖
pip install -r requirements.txt

# 6. 配置系统服务
sudo nano /etc/systemd/system/idle-scheduler.service
系统服务文件：

ini
# /etc/systemd/system/idle-scheduler.service
[Unit]
Description=Idle Computing Scheduler
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/idle-accelerator
Environment="PATH=/home/ubuntu/idle-accelerator/venv/bin"
ExecStart=/home/ubuntu/idle-accelerator/venv/bin/uvicorn scheduler.simple_server:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
启动服务：

bash
sudo systemctl daemon-reload
sudo systemctl enable idle-scheduler
sudo systemctl start idle-scheduler
sudo systemctl status idle-scheduler  # 检查状态
方案B：Nginx反向代理 + HTTPS
nginx
# /etc/nginx/sites-available/idle-accelerator
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL证书（Let's Encrypt）
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # 调度中心API
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 网页界面
    location / {
        proxy_pass http://localhost:8501/;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    # 静态文件缓存
    location /static/ {
        alias /home/ubuntu/idle-accelerator/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
📱 客户端节点部署
Windows节点
下载安装包：从Releases页面下载 idle-node-windows.exe

配置连接：

bash
# 创建配置文件 C:\Users\用户名\.idle-accelerator\config.yaml
scheduler_url: "http://your-server.com:8000"
node_name: "my-windows-pc"
check_interval: 30
运行服务：

bash
# 作为系统服务安装
idle-node-windows.exe --install-service
# 或手动运行
idle-node-windows.exe
macOS节点
bash
# 1. 安装Homebrew（如未安装）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. 安装Python和项目
brew install python
pip install idle-accelerator-node

# 3. 配置和运行
idle-node --scheduler http://your-server.com:8000 --name "my-macbook"

# 4. 设置为登录项（可选）
cp idle-node.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/idle-node.plist
Linux节点
bash
# 1. 安装依赖
sudo apt update
sudo apt install -y python3-pip

# 2. 安装节点
pip3 install idle-accelerator-node --user

# 3. 配置systemd服务
sudo nano /etc/systemd/system/idle-node.service
服务文件：

ini
[Unit]
Description=Idle Computing Node
After=network.target

[Service]
Type=simple
User=pi  # 树莓派用户或其他
ExecStart=/usr/local/bin/idle-node --scheduler http://your-server.com:8000 --name "raspberry-pi"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
🔧 配置管理
markdown 复制   下载    ## ⚖️ 公平调度配置

### 调度算法配置
为了实现 **贡献奖励** 与 **新人机会** 的平衡，系统提供可配置的调度策略：

```yaml
# config/scheduler.yaml
scheduling:
  # 调度策略选择
  policy: "fair_priority"  # 可选: fifo(先进先出), priority(优先级), fair_priority(公平优先级)
  
  # 公平优先级算法配置
  fair_priority:
    # 权重分配（总和应为1.0）
    weights:
      wait_time: 0.6      # 等待时间权重（60%）
      contribution: 0.3   # 贡献度权重（30%）
      newcomer: 0.1       # 新人加成权重（10%）
    
    # 贡献度奖励上限（防止过度倾斜）
    contribution_cap: 10.0  # 最多加10分
    
    # 新人保护
    newcomer_threshold: 10   # 前10个任务视为新人
    newcomer_base_bonus: 20  # 新人基础加成
    
    # 防饥饿机制
    starvation_threshold: 300  # 等待300秒（5分钟）自动升为最高优先级
    
    # 冷却时间（刚执行过的节点暂时降低优先级）
    cooldown_period: 1800  # 30分钟内执行过任务的节点降低优先级  配置示例 示例1：完全公平（适合公益项目） yaml 复制   下载    scheduling:
  policy: "fair_priority"
  fair_priority:
    weights:
      wait_time: 0.8      # 主要看等待时间
      contribution: 0.1   # 少量贡献奖励
      newcomer: 0.1       # 少量新人加成
    contribution_cap: 5.0  # 低上限
    newcomer_threshold: 20 # 宽松的新人定义  示例2：贡献激励（适合社区项目） yaml 复制   下载    scheduling:
  policy: "fair_priority"
  fair_priority:
    weights:
      wait_time: 0.5      # 等待时间占一半
      contribution: 0.4   # 较重贡献奖励
      newcomer: 0.1       # 保持新人机会
    contribution_cap: 15.0 # 较高上限
    starvation_threshold: 600 # 10分钟防饥饿  示例3：简单先进先出（适合小规模测试） yaml 复制   下载    scheduling:
  policy: "fifo"  # 最简单的先进先出  动态调整调度策略 bash 复制   下载    # 运行时查看当前调度状态
curl http://localhost:8000/stats/scheduling

# 响应示例
{
  "policy": "fair_priority",
  "active_nodes": 8,
  "queue_size": 12,
  "avg_wait_time": 45.2,
  "distribution": {
    "new_nodes_served": 3,
    "high_contributors_served": 5,
    "starving_nodes": 0
  }
}

# 动态调整权重（需要管理员权限）
curl -X PATCH http://localhost:8000/admin/scheduling \
  -H "Content-Type: application/json" \
  -d '{"weights": {"wait_time": 0.7, "contribution": 0.2, "newcomer": 0.1}}'  监控公平性指标 bash 复制   下载    # 查看调度公平性报告
curl http://localhost:8000/stats/fairness

# 响应包含：
{
  "gini_coefficient": 0.25,      # 基尼系数（0最公平，1最不公平）
  "min_wait_time": 5.2,          # 最短等待时间（秒）
  "max_wait_time": 305.8,        # 最长等待时间（秒）
  "avg_wait_time": 45.3,         # 平均等待时间
  "new_node_success_rate": 0.85, # 新节点获得任务比例
  "long_wait_nodes": 1           # 等待超时的节点数
}  生产环境建议 1.  初始设置：使用中等权重（0.6等待时间，0.3贡献，0.1新人）  2.  监控调整：根据基尼系数调整权重，保持在0.2-0.3之间  3.  定期评估：每周查看公平性报告，确保没有节点"饿死"  4.  特殊情况：对科研节点等可配置白名单，给予固定优先级   调度算法实现位置 python 复制   下载    # 调度算法实现在：
# scheduler/fair_scheduler.py

class FairPriorityScheduler:
    def __init__(self, config):
        self.weights = config['weights']
        self.contribution_cap = config['contribution_cap']
        
    def calculate_score(self, node):
        """计算节点调度分数（分数低者优先）"""
        # 等待时间分数（等待越久分数越低）
        wait_score = -node.wait_time * self.weights['wait_time']
        
        # 贡献度分数（贡献越多分数越低，但有上限）
        contribution = min(node.completed_tasks * 0.1, self.contribution_cap)
        contrib_score = -contribution * self.weights['contribution']
        
        # 新人加成（前N个任务有额外加分）
        newcomer_score = 0
        if node.completed_tasks < self.newcomer_threshold:
            bonus = self.newcomer_base_bonus - node.completed_tasks * 2
            newcomer_score = -bonus * self.weights['newcomer']
        
        # 防饥饿：等待超时直接最高优先级
        if node.wait_time > self.starvation_threshold:
            return float('-inf')
        
        # 冷却期：最近执行过降低优先级
        if time.time() - node.last_task_time < self.cooldown_period:
            wait_score *= 0.5  # 降低等待时间权重
        
        return wait_score + contrib_score + newcomer_score
环境变量配置
bash
# 调度中心配置
export SCHEDULER_HOST=0.0.0.0
export SCHEDULER_PORT=8000
export LOG_LEVEL=INFO
export MAX_QUEUE_SIZE=1000

# 节点配置
export SCHEDULER_URL=http://localhost:8000
export NODE_NAME=${HOSTNAME}
export CHECK_INTERVAL=30
export IDLE_THRESHOLD=300  # 5分钟
export MAX_TASK_TIME=300   # 任务最长5分钟
配置文件示例
yaml
# config/config.yaml
# 调度中心配置
scheduler:
  host: "0.0.0.0"
  port: 8000
  log_level: "INFO"
  redis:
    enabled: false  # 开发环境可不启用
    url: "redis://localhost:6379/0"
  
  # 任务队列配置
  tasks:
    max_queue_size: 1000
    result_ttl: 3600  # 结果保留1小时
    cleanup_interval: 60  # 清理间隔

# 节点配置
node:
  scheduler_url: "http://localhost:8000"
  node_name: "my-computer"
  
  # 闲置检测配置
  idle_detection:
    check_interval: 30
    idle_threshold: 300
    cpu_threshold: 30.0
    memory_threshold: 70.0
    
  # 安全配置
  security:
    max_task_time: 300
    max_memory_mb: 1024
    network_access: false  # 默认禁止网络
    auto_cleanup: true
    
  # 资源限制
  resources:
    max_cpu_cores: 2.0
    max_memory_mb: 4096
    max_disk_mb: 100
📊 监控与维护
健康检查
bash
# 检查调度中心
curl http://localhost:8000/health

# 检查节点状态
curl http://localhost:8000/nodes

# 查看任务队列
curl http://localhost:8000/tasks?status=pending
日志查看
bash
# 调度中心日志
journalctl -u idle-scheduler -f

# 节点日志（如果配置了systemd）
journalctl -u idle-node -f

# 或查看文件日志
tail -f /var/log/idle-accelerator/scheduler.log
性能监控
bash
# 安装监控工具
pip install prometheus-client

# 启用指标端点（在调度中心配置中）
# metrics_endpoint: true
# 然后访问 http://localhost:8000/metrics
关键监控指标：

idle_nodes_count：当前闲置节点数

tasks_queue_size：等待任务数

tasks_completed_total：完成任务总数

node_cpu_usage：各节点CPU使用率

node_memory_usage：各节点内存使用率

🚨 故障排除
常见问题
1. 节点无法连接调度中心
bash
# 检查网络连通性
ping your-server.com
curl -v http://your-server.com:8000/health

# 检查防火墙
sudo ufw status  # Ubuntu
sudo firewall-cmd --list-all  # CentOS
2. 任务执行失败
bash
# 查看任务详情
curl http://localhost:8000/tasks/failed-task-id

# 检查节点资源
python -c "from idle_sense import get_system_status; print(get_system_status())"

# 增加资源限制
export MAX_TASK_TIME=600
export MAX_MEMORY_MB=2048
3. 内存不足
bash
# 查看内存使用
free -h
htop

# 调整节点配置
# 在config.yaml中减少max_memory_mb
# 或增加系统交换空间
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
4. 调度中心崩溃
bash
# 查看错误日志
journalctl -u idle-scheduler --since "5 minutes ago"

# 重启服务
sudo systemctl restart idle-scheduler

# 如果是内存不足，增加服务内存限制
# 编辑systemd服务文件，添加：
# MemoryMax=2G
# MemorySwapMax=4G
调试模式
bash
# 启用详细日志
export LOG_LEVEL=DEBUG

# 调试调度中心
uvicorn scheduler.simple_server:app --reload --log-level debug

# 调试节点
python node/simple_client.py --debug --log-file debug.log
🔄 更新与升级
平滑升级步骤
备份配置和数据

bash
cp -r ~/.idle-accelerator ~/.idle-accelerator.backup
停止服务

bash
sudo systemctl stop idle-scheduler
sudo systemctl stop idle-node  # 在所有节点上
更新代码

bash
cd idle-accelerator
git pull origin main
pip install -r requirements.txt --upgrade
重启服务

bash
sudo systemctl start idle-scheduler
sudo systemctl start idle-node
验证升级

bash
curl http://localhost:8000/health
sudo systemctl status idle-scheduler
📈 规模化部署建议
中小规模（<100节点）
单调度中心 + Redis缓存

节点直接连接调度中心

使用Nginx负载均衡（可选）

中大规模（100-1000节点）
多调度中心实例 + Redis集群

负载均衡器分发请求

分区部署（按地理区域）

超大规模（>1000节点）
多区域部署

边缘计算节点

去中心化调度（未来版本）

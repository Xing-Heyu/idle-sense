# 部署指南

## 🚀 快速部署

### 单机部署（开发环境）

#### 步骤1: 环境准备

```bash
# 1.1 安装 Python 3.9+
python --version

# 1.2 安装依赖管理工具
pip install --upgrade pip

# 1.3 克隆项目代码
git clone https://github.com/Xing-Heyu/idle-sense.git
cd idle-sense
```

#### 步骤2: 安装依赖

```bash
# 2.1 创建虚拟环境
python -m venv venv

# 2.2 激活虚拟环境
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 2.3 安装依赖包
pip install -r requirements.txt
```

#### 步骤3: 配置服务

```bash
# 3.1 复制配置文件
cp config/config.yaml.example config/config.yaml

# 3.2 复制环境变量文件
cp .env.example .env

# 3.3 创建必要目录
mkdir -p logs data
```

#### 步骤4: 启动服务

```bash
# 4.1 启动调度中心（终端1）
python -m legacy.scheduler.simple_server

# 4.2 启动计算节点（终端2）
python -m legacy.node.simple_client --scheduler http://localhost:8000

# 4.3 启动网页界面（终端3，可选）
streamlit run src/presentation/streamlit/app.py
```

#### 步骤5: 验证部署

```bash
# 5.1 检查调度中心
curl http://localhost:8000/

# 5.2 运行测试脚本
python scripts/quick_test.py

# 5.3 访问网页界面
# 浏览器打开: http://localhost:8501
```

## 🐳 Docker 部署

### 使用 Docker Compose

#### docker-compose.yml 配置

```yaml
version: '3.8'

services:
  scheduler:
    image: python:3.11-slim
    container_name: idle-scheduler
    ports:
      - "8000:8000"
    volumes:
      - ./legacy/scheduler:/app/scheduler
      - ./legacy/idle_sense:/app/idle_sense
      - ./requirements.txt:/app/requirements.txt
      - ./config/config.yaml:/app/config.yaml
    working_dir: /app
    command: >
      sh -c "pip install -r requirements.txt &&
             uvicorn legacy.scheduler.simple_server:app --host 0.0.0.0 --port 8000"
    restart: unless-stopped

  node:
    image: python:3.11-slim
    container_name: idle-node
    volumes:
      - ./legacy/node:/app/node
      - ./legacy/idle_sense:/app/idle_sense
      - ./requirements.txt:/app/requirements.txt
    working_dir: /app
    environment:
      - SCHEDULER_URL=http://scheduler:8000
    command: >
      sh -c "pip install -r requirements.txt &&
             python -m legacy.node.simple_client --scheduler http://scheduler:8000"
    depends_on:
      - scheduler
    restart: unless-stopped

  web:
    image: python:3.11-slim
    container_name: idle-web
    ports:
      - "8501:8501"
    volumes:
      - ./src/presentation/streamlit:/app/streamlit
      - ./requirements.txt:/app/requirements.txt
    working_dir: /app
    command: >
      sh -c "pip install -r requirements.txt &&
             streamlit run streamlit/app.py --server.port 8501 --server.address 0.0.0.0"
    depends_on:
      - scheduler
    restart: unless-stopped
```

#### 启动命令

```bash
# 1. 启动所有服务
docker-compose up -d

# 2. 查看服务状态
docker-compose ps

# 3. 查看日志
docker-compose logs -f scheduler

# 4. 停止服务
docker-compose down

# 5. 重建服务（修改配置后）
docker-compose up -d --build
```

### 构建自定义镜像

#### Dockerfile.scheduler

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY legacy/scheduler/ ./scheduler/
COPY legacy/idle_sense/ ./idle_sense/
COPY config/config.yaml ./config/

EXPOSE 8000

CMD ["uvicorn", "legacy.scheduler.simple_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 构建和运行

```bash
# 构建镜像
docker build -f Dockerfile.scheduler -t idle-scheduler:latest .

# 运行容器
docker run -d \
  --name idle-scheduler \
  -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  idle-scheduler:latest
```

## ☁️ 云服务器部署

### Ubuntu 20.04+ 服务器

#### 自动安装脚本

```bash
# 1. 下载安装脚本
wget https://raw.githubusercontent.com/Xing-Heyu/idle-sense/main/scripts/setup_scheduler.sh

# 2. 赋予执行权限
chmod +x setup_scheduler.sh

# 3. 运行安装脚本
sudo ./setup_scheduler.sh
```

#### 手动安装步骤

```bash
# 1. 更新系统
sudo apt update
sudo apt upgrade -y

# 2. 安装基础依赖
sudo apt install -y python3-pip python3-venv git nginx

# 3. 创建系统用户
sudo useradd -r -s /bin/false idleuser

# 4. 创建应用目录
sudo mkdir -p /opt/idle-sense
sudo chown -R idleuser:idleuser /opt/idle-sense

# 5. 克隆代码
sudo -u idleuser git clone https://github.com/Xing-Heyu/idle-sense /opt/idle-sense

# 6. 安装Python依赖
cd /opt/idle-sense
sudo -u idleuser python3 -m venv venv
sudo -u idleuser venv/bin/pip install -r requirements.txt
```

### Systemd 服务配置

#### /etc/systemd/system/idle-scheduler.service

```ini
[Unit]
Description=Idle Computing Scheduler
After=network.target
Wants=network.target

[Service]
Type=simple
User=idleuser
Group=idleuser
WorkingDirectory=/opt/idle-sense
Environment="PATH=/opt/idle-sense/venv/bin"
EnvironmentFile=/opt/idle-sense/.env
ExecStart=/opt/idle-sense/venv/bin/uvicorn legacy.scheduler.simple_server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=idle-scheduler

# 安全限制
NoNewPrivileges=true
ProtectSystem=strict
PrivateTmp=true
PrivateDevices=true
ProtectHome=true
ReadWritePaths=/opt/idle-sense/logs /opt/idle-sense/data

[Install]
WantedBy=multi-user.target
```

#### 管理服务

```bash
# 1. 重载systemd配置
sudo systemctl daemon-reload

# 2. 启用服务
sudo systemctl enable idle-scheduler

# 3. 启动服务
sudo systemctl start idle-scheduler

# 4. 查看状态
sudo systemctl status idle-scheduler

# 5. 查看日志
sudo journalctl -u idle-scheduler -f
```

### Nginx 反向代理配置

#### /etc/nginx/sites-available/idle-sense

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # 静态文件缓存
    location /static/ {
        alias /opt/idle-sense/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # 客户端上传限制
    client_max_body_size 10M;
    
    # 超时设置
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
}
```

### SSL/TLS 配置（Let's Encrypt）

```bash
# 1. 安装Certbot
sudo apt install -y certbot python3-certbot-nginx

# 2. 获取证书
sudo certbot --nginx -d your-domain.com

# 3. 自动续期测试
sudo certbot renew --dry-run
```

## 📱 客户端节点部署

### Windows 节点

```powershell
# 1. 下载Windows安装包
Invoke-WebRequest -Uri "https://github.com/Xing-Heyu/idle-sense/releases/latest/download/idle-node-windows.exe" -OutFile "idle-node.exe"

# 2. 创建配置文件
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.idle-sense"
@"
node:
  scheduler_url: "http://your-server.com:8000"
  node_name: "$env:COMPUTERNAME"
  idle_detection:
    check_interval: 30
    idle_threshold: 300
"@ | Out-File "$env:USERPROFILE\.idle-sense\config.yaml"

# 3. 注册为Windows服务
.\idle-node.exe install
Start-Service IdleNode
```

### macOS 节点

```bash
# 1. 使用Homebrew安装
brew tap Xing-Heyu/idle-sense
brew install idle-sense-node

# 2. 配置服务
idle-node configure --scheduler http://your-server.com:8000 --name $(hostname)

# 3. 启动服务
brew services start idle-sense-node
```

### Linux 节点（脚本安装）

```bash
# 1. 下载安装脚本
curl -fsSL https://raw.githubusercontent.com/Xing-Heyu/idle-sense/main/scripts/setup_node.sh -o setup_node.sh

# 2. 运行安装
chmod +x setup_node.sh
./setup_node.sh
```

## 🔧 配置说明

### 核心配置项

#### config/config.yaml

```yaml
# 调度中心配置
scheduler:
  host: "0.0.0.0"
  port: 8000
  log_level: "INFO"
  
  # 任务队列配置
  tasks:
    max_queue_size: 1000
    result_ttl: 3600
    cleanup_interval: 60
  
  # 调度算法配置
  scheduling:
    policy: "fair_priority"
    fair_priority:
      weights:
        wait_time: 0.6
        contribution: 0.3
        newcomer: 0.1

# 节点客户端配置
node:
  scheduler_url: "http://localhost:8000"
  node_name: "${HOSTNAME}"
  
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
    network_access: false
    auto_cleanup: true
```

### 环境变量配置

#### .env 文件

```bash
# 调度中心配置
SCHEDULER_HOST=0.0.0.0
SCHEDULER_PORT=8000
SCHEDULER_LOG_LEVEL=INFO

# 节点配置
NODE_SCHEDULER_URL=http://localhost:8000
NODE_NAME=${HOSTNAME}
NODE_CHECK_INTERVAL=30
NODE_IDLE_THRESHOLD=300

# 数据库配置（可选）
REDIS_URL=redis://localhost:6379/0

# 安全配置
REQUIRE_AUTH=false
ALLOWED_ORIGINS=*
```

## 📊 监控和维护

### 健康检查端点

```bash
# 基本健康检查
curl http://localhost:8000/health

# 详细状态
curl http://localhost:8000/stats

# 节点状态
curl http://localhost:8000/api/nodes
```

### 日志管理

```bash
# 查看调度中心日志
tail -f /opt/idle-sense/logs/scheduler.log

# 查看systemd日志
sudo journalctl -u idle-scheduler -f

# 日志轮转配置（/etc/logrotate.d/idle-sense）
/opt/idle-sense/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 640 idleuser idleuser
}
```

### 备份和恢复

```bash
# 创建备份
BACKUP_DIR="/backup/idle-sense/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR
cp -r /opt/idle-sense/config $BACKUP_DIR/
cp -r /opt/idle-sense/data $BACKUP_DIR/
tar -czf $BACKUP_DIR/backup.tar.gz $BACKUP_DIR/*

# 恢复备份
tar -xzf backup.tar.gz -C /opt/idle-sense/
sudo systemctl restart idle-scheduler
```

## 🚨 故障排除

### 常见问题

#### 端口冲突

```bash
# 检查端口占用
sudo lsof -i :8000

# 更改端口
python -m legacy.scheduler.simple_server --port 8080
```

#### 服务无法启动

```bash
# 检查日志
sudo journalctl -u idle-scheduler --no-pager -n 50

# 测试手动启动
sudo -u idleuser /opt/idle-sense/venv/bin/python -m legacy.scheduler.simple_server
```

#### 节点无法连接

```bash
# 测试网络连接
ping your-server.com
telnet your-server.com 8000

# 检查防火墙
sudo ufw status
sudo ufw allow 8000/tcp
```

### 性能调优

#### 调整系统参数

```bash
# 增加文件描述符限制
echo "* soft nofile 65535" >> /etc/security/limits.conf
echo "* hard nofile 65535" >> /etc/security/limits.conf

# 调整内核参数
echo "net.core.somaxconn = 1024" >> /etc/sysctl.conf
echo "vm.overcommit_memory = 1" >> /etc/sysctl.conf
sysctl -p
```

#### 数据库优化（如果使用Redis）

```bash
# Redis配置优化
maxmemory 1gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

## 🔄 升级流程

### 平滑升级步骤

```bash
# 1. 停止服务
sudo systemctl stop idle-scheduler

# 2. 备份当前版本
cp -r /opt/idle-sense /opt/idle-sense.backup.$(date +%Y%m%d)

# 3. 更新代码
cd /opt/idle-sense
sudo -u idleuser git pull origin main

# 4. 更新依赖
sudo -u idleuser venv/bin/pip install -r requirements.txt --upgrade

# 5. 运行数据库迁移（如果有）
# sudo -u idleuser venv/bin/python manage.py migrate

# 6. 重启服务
sudo systemctl start idle-scheduler

# 7. 验证升级
curl http://localhost:8000/health
```

### 回滚步骤

```bash
# 1. 停止服务
sudo systemctl stop idle-scheduler

# 2. 恢复备份
rm -rf /opt/idle-sense
cp -r /opt/idle-sense.backup.20240101 /opt/idle-sense

# 3. 重启服务
sudo systemctl start idle-scheduler
```

---

**最后更新**: 2026-03-28

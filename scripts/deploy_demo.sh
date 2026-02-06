#!/bin/bash
# scripts/deploy_demo.sh
# 一键部署演示环境（调度中心 + 网页界面）

set -e

echo "🚀 闲置计算加速器 - 演示环境部署"
echo "========================================"

# 设置颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${YELLOW}Docker未安装，开始安装...${NC}"
        
        # 根据系统安装Docker
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            curl -fsSL https://get.docker.com -o get-docker.sh
            sudo sh get-docker.sh
            sudo usermod -aG docker $USER
            rm get-docker.sh
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            echo "请从 https://docs.docker.com/desktop/install/mac-install/ 安装Docker Desktop"
            exit 1
        fi
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${YELLOW}安装docker-compose...${NC}"
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi
    
    echo -e "${GREEN}✓ Docker环境就绪${NC}"
}

# 创建演示配置
create_demo_config() {
    echo -e "${YELLOW}创建演示配置...${NC}"
    
    mkdir -p demo-config
    
    # 创建docker-compose文件
    cat > docker-compose.demo.yml << 'EOF'
version: '3.8'

services:
  # 调度中心
  scheduler:
    image: python:3.11-slim
    container_name: idle-scheduler-demo
    working_dir: /app
    ports:
      - "8000:8000"
    volumes:
      - ./scheduler:/app/scheduler
      - ./idle_sense:/app/idle_sense
      - ./requirements.txt:/app/requirements.txt
      - ./demo-config/scheduler-config.yaml:/app/config.yaml
    command: >
      sh -c "pip install -r requirements.txt &&
             uvicorn scheduler.simple_server:app --host 0.0.0.0 --port 8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  # 网页界面
  web:
    image: python:3.11-slim
    container_name: idle-web-demo
    working_dir: /app
    ports:
      - "8501:8501"
    volumes:
      - ./web_interface.py:/app/web_interface.py
      - ./requirements.txt:/app/requirements.txt
    command: >
      sh -c "pip install -r requirements.txt &&
             streamlit run web_interface.py --server.port 8501 --server.address 0.0.0.0"
    depends_on:
      - scheduler
    restart: unless-stopped

  # 模拟节点1 (Windows模拟)
  node1:
    image: python:3.11-slim
    container_name: idle-node1-demo
    working_dir: /app
    volumes:
      - ./node:/app/node
      - ./idle_sense:/app/idle_sense
      - ./requirements.txt:/app/requirements.txt
      - ./demo-config/node1-config.yaml:/app/config.yaml
    environment:
      - PLATFORM=Windows
      - NODE_NAME=demo-windows-node
      - SCHEDULER_URL=http://scheduler:8000
    command: >
      sh -c "pip install -r requirements.txt &&
             echo '模拟Windows节点启动...' &&
             while true; do
               echo '节点运行中...';
               sleep 30;
             done"
    depends_on:
      - scheduler
    restart: unless-stopped

  # 模拟节点2 (macOS模拟)
  node2:
    image: python:3.11-slim
    container_name: idle-node2-demo
    working_dir: /app
    volumes:
      - ./node:/app/node
      - ./idle_sense:/app/idle_sense
      - ./requirements.txt:/app/requirements.txt
      - ./demo-config/node2-config.yaml:/app/config.yaml
    environment:
      - PLATFORM=macOS
      - NODE_NAME=demo-macos-node
      - SCHEDULER_URL=http://scheduler:8000
    command: >
      sh -c "pip install -r requirements.txt &&
             echo '模拟macOS节点启动...' &&
             while true; do
               echo '节点运行中...';
               sleep 30;
             done"
    depends_on:
      - scheduler
    restart: unless-stopped

  # 监控面板 (可选)
  monitor:
    image: prom/prometheus:latest
    container_name: idle-monitor-demo
    ports:
      - "9090:9090"
    volumes:
      - ./demo-config/prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/console_templates'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'
    restart: unless-stopped
EOF

    # 创建调度中心配置
    cat > demo-config/scheduler-config.yaml << 'EOF'
scheduler:
  host: "0.0.0.0"
  port: 8000
  log_level: "INFO"
  
  tasks:
    max_queue_size: 100
    result_ttl: 3600
    
  scheduling:
    policy: "fair_priority"
    fair_priority:
      weights:
        wait_time: 0.6
        contribution: 0.3
        newcomer: 0.1
      newcomer_threshold: 5
EOF

    # 创建节点配置
    cat > demo-config/node1-config.yaml << 'EOF'
node:
  scheduler_url: "http://scheduler:8000"
  node_name: "demo-windows-node"
  
  idle_detection:
    check_interval: 10
    idle_threshold: 30
    
  security:
    max_task_time: 60
    max_memory_mb: 256
EOF

    cat > demo-config/node2-config.yaml << 'EOF'
node:
  scheduler_url: "http://scheduler:8000"
  node_name: "demo-macos-node"
  
  idle_detection:
    check_interval: 10
    idle_threshold: 30
    
  security:
    max_task_time: 60
    max_memory_mb: 256
EOF

    # 创建Prometheus配置
    cat > demo-config/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'idle-scheduler'
    static_configs:
      - targets: ['scheduler:8000']
    
  - job_name: 'idle-nodes'
    static_configs:
      - targets: ['node1:8000', 'node2:8000']
EOF

    echo -e "${GREEN}✓ 演示配置已创建${NC}"
}

# 启动演示环境
start_demo() {
    echo -e "${YELLOW}启动演示环境...${NC}"
    
    # 检查是否已有运行中的容器
    if [ "$(docker ps -q -f name=idle-)" ]; then
        echo -e "${YELLOW}停止现有演示环境...${NC}"
        docker-compose -f docker-compose.demo.yml down
    fi
    
    # 启动新环境
    docker-compose -f docker-compose.demo.yml up -d
    
    echo -e "${GREEN}✓ 演示环境已启动${NC}"
    sleep 3  # 等待服务启动
}

# 显示访问信息
show_access_info() {
    LOCAL_IP=$(hostname -I | awk '{print $1}')
    if [ -z "$LOCAL_IP" ]; then
        LOCAL_IP="localhost"
    fi
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}🎉 演示环境部署完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "🌐 访问地址:"
    echo "  • 调度中心API: http://$LOCAL_IP:8000"
    echo "  • 网页控制台: http://$LOCAL_IP:8501"
    echo "  • 监控面板: http://$LOCAL_IP:9090"
    echo ""
    echo "🖥️  运行中的容器:"
    docker ps --filter "name=idle-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo "🔧 管理命令:"
    echo "  • 查看日志: docker-compose -f docker-compose.demo.yml logs -f"
    echo "  • 停止环境: docker-compose -f docker-compose.demo.yml down"
    echo "  • 重启环境: docker-compose -f docker-compose.demo.yml restart"
    echo ""
    echo "🚀 快速测试:"
    echo "  1. 打开网页: http://$LOCAL_IP:8501"
    echo "  2. 提交示例任务"
    echo "  3. 查看任务执行状态"
    echo ""
    echo -e "${YELLOW}演示环境包含:${NC}"
    echo "  • 1个调度中心"
    echo "  • 1个网页界面"
    echo "  • 2个模拟计算节点"
    echo "  • 1个监控面板 (Prometheus)"
    echo ""
}

# 运行健康检查
health_check() {
    echo -e "${YELLOW}运行健康检查...${NC}"
    
    # 检查调度中心
    if curl -s http://localhost:8000/ > /dev/null; then
        echo -e "${GREEN}✓ 调度中心: 运行正常${NC}"
    else
        echo -e "${YELLOW}⚠  调度中心: 启动中...${NC}"
    fi
    
    # 检查网页界面
    if curl -s http://localhost:8501 > /dev/null; then
        echo -e "${GREEN}✓ 网页界面: 运行正常${NC}"
    else
        echo -e "${YELLOW}⚠  网页界面: 启动中...${NC}"
    fi
    
    echo -e "${YELLOW}等待服务完全启动...${NC}"
    sleep 5
}

# 主函数
main() {
    check_docker
    create_demo_config
    start_demo
    health_check
    show_access_info
    
    echo ""
    echo -e "${GREEN}演示环境已就绪，可以开始展示！${NC}"
}

# 运行主函数
main "$@"

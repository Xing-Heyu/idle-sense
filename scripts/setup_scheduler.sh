#!/bin/bash
# scripts/setup_scheduler.sh
# 调度中心一键安装脚本
# 适用于 Ubuntu/Debian/CentOS/macOS

set -e  # 出错时退出

echo "⚡ 闲置计算加速器 - 调度中心安装脚本"
echo "========================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查操作系统
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    elif type lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si | tr '[:upper:]' '[:lower:]')
        VER=$(lsb_release -sr)
    elif [ -f /etc/redhat-release ]; then
        OS="centos"
        VER=$(cat /etc/redhat-release | sed 's/[^0-9.]*\([0-9.]\).*/\1/')
    else
        OS=$(uname -s | tr '[:upper:]' '[:lower:]')
        VER=$(uname -r)
    fi
    echo "检测到系统: $OS $VER"
}

# 检查依赖
check_dependencies() {
    echo -e "${YELLOW}[1/6] 检查系统依赖...${NC}"
    
    local missing_deps=()
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    fi
    
    if ! command -v pip3 &> /dev/null; then
        missing_deps+=("python3-pip")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        echo -e "${YELLOW}缺少依赖: ${missing_deps[*]}${NC}"
        install_dependencies "${missing_deps[@]}"
    else
        echo -e "${GREEN}✓ 所有依赖已安装${NC}"
    fi
}

# 安装依赖
install_dependencies() {
    echo -e "${YELLOW}安装依赖: $*${NC}"
    
    case $OS in
        ubuntu|debian)
            sudo apt-get update
            sudo apt-get install -y "$@"
            ;;
        centos|rhel|fedora)
            sudo yum install -y "$@"
            ;;
        darwin|macos)
            if ! command -v brew &> /dev/null; then
                echo -e "${RED}请先安装 Homebrew: https://brew.sh/${NC}"
                exit 1
            fi
            brew install "$@"
            ;;
        *)
            echo -e "${RED}不支持的操作系统: $OS${NC}"
            echo "请手动安装: $*"
            exit 1
            ;;
    esac
}

# 创建项目目录
setup_project_dir() {
    echo -e "${YELLOW}[2/6] 设置项目目录...${NC}"
    
    # 默认安装目录
    DEFAULT_DIR="$HOME/idle-accelerator"
    
    read -p "安装目录 [$DEFAULT_DIR]: " INSTALL_DIR
    INSTALL_DIR=${INSTALL_DIR:-$DEFAULT_DIR}
    
    # 创建目录
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    echo -e "${GREEN}✓ 项目目录: $INSTALL_DIR${NC}"
}

# 克隆或复制项目文件
setup_project_files() {
    echo -e "${YELLOW}[3/6] 设置项目文件...${NC}"
    
    # 检查是否在Git仓库中
    if [ -d ".git" ]; then
        echo -e "${GREEN}✓ 已在Git仓库中，拉取更新...${NC}"
        git pull origin main
    else
        # 询问是否从GitHub克隆
        read -p "从GitHub克隆项目？(y/n) [y]: " CLONE_GIT
        CLONE_GIT=${CLONE_GIT:-y}
        
        if [[ $CLONE_GIT =~ ^[Yy]$ ]]; then
            GIT_REPO="https://github.com/your-username/idle-accelerator.git"
            read -p "GitHub仓库URL [$GIT_REPO]: " INPUT_REPO
            GIT_REPO=${INPUT_REPO:-$GIT_REPO}
            
            git clone "$GIT_REPO" .
            echo -e "${GREEN}✓ 从GitHub克隆完成${NC}"
        else
            # 手动复制模式
            echo "请将项目文件复制到: $INSTALL_DIR"
            echo "按回车键继续..."
            read -r
        fi
    fi
}

# 安装Python依赖
install_python_deps() {
    echo -e "${YELLOW}[4/6] 安装Python依赖...${NC}"
    
    # 检查requirements.txt
    if [ ! -f "requirements.txt" ]; then
        echo -e "${RED}✗ 未找到 requirements.txt${NC}"
        echo "创建基本的requirements.txt..."
        cat > requirements.txt << EOF
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
psutil>=5.9.0
requests>=2.31.0
streamlit>=1.28.0
python-multipart>=0.0.6
EOF
    fi
    
    # 创建虚拟环境
    if [ ! -d "venv" ]; then
        echo "创建Python虚拟环境..."
        python3 -m venv venv
    fi
    
    # 激活虚拟环境并安装
    echo "安装依赖包..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    echo -e "${GREEN}✓ Python依赖安装完成${NC}"
}

# 配置调度中心
configure_scheduler() {
    echo -e "${YELLOW}[5/6] 配置调度中心...${NC}"
    
    # 创建配置目录
    mkdir -p config logs data
    
    # 复制配置文件模板
    if [ -f "config/config.yaml.example" ] && [ ! -f "config/config.yaml" ]; then
        cp config/config.yaml.example config/config.yaml
        echo -e "${GREEN}✓ 配置文件已创建: config/config.yaml${NC}"
        echo -e "${YELLOW}  请编辑此文件进行配置${NC}"
    fi
    
    # 创建环境文件
    if [ ! -f ".env" ]; then
        cat > .env << EOF
# 调度中心配置
SCHEDULER_HOST=0.0.0.0
SCHEDULER_PORT=8000
SCHEDULER_LOG_LEVEL=INFO

# Redis配置（可选）
REDIS_ENABLED=false
REDIS_URL=redis://localhost:6379/0

# 安全配置
REQUIRE_AUTH=false
ALLOWED_ORIGINS=*
EOF
        echo -e "${GREEN}✓ 环境文件已创建: .env${NC}"
    fi
    
    # 创建systemd服务文件
    if [ "$OS" != "darwin" ] && [ "$OS" != "macos" ]; then
        create_systemd_service
    fi
}

# 创建systemd服务
create_systemd_service() {
    echo -e "${YELLOW}创建systemd服务...${NC}"
    
    SERVICE_FILE="/etc/systemd/system/idle-scheduler.service"
    
    if [ -f "$SERVICE_FILE" ]; then
        echo -e "${YELLOW}systemd服务已存在${NC}"
        return
    fi
    
    cat << EOF | sudo tee "$SERVICE_FILE" > /dev/null
[Unit]
Description=Idle Computing Scheduler
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/uvicorn scheduler.simple_server:app --host \${SCHEDULER_HOST} --port \${SCHEDULER_PORT}
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
ReadWritePaths=$INSTALL_DIR/logs $INSTALL_DIR/data

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    echo -e "${GREEN}✓ systemd服务已创建${NC}"
    
    read -p "启用并启动服务？(y/n) [y]: " ENABLE_SERVICE
    ENABLE_SERVICE=${ENABLE_SERVICE:-y}
    
    if [[ $ENABLE_SERVICE =~ ^[Yy]$ ]]; then
        sudo systemctl enable idle-scheduler
        sudo systemctl start idle-scheduler
        echo -e "${GREEN}✓ 服务已启用并启动${NC}"
        
        # 检查状态
        sleep 2
        sudo systemctl status idle-scheduler --no-pager
    fi
}

# 完成安装
finish_installation() {
    echo -e "${YELLOW}[6/6] 完成安装...${NC}"
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}🎉 调度中心安装完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "📁 项目目录: $INSTALL_DIR"
    echo "🌐 调度中心URL: http://$(hostname -I | awk '{print $1}'):8000"
    echo "📊 健康检查: http://$(hostname -I | awk '{print $1}'):8000/health"
    echo ""
    echo "📋 后续步骤:"
    echo "  1. 编辑配置文件: nano $INSTALL_DIR/config/config.yaml"
    echo "  2. 启动服务:"
    if [ -f "/etc/systemd/system/idle-scheduler.service" ]; then
        echo "     sudo systemctl start idle-scheduler"
    else
        echo "     cd $INSTALL_DIR && source venv/bin/activate"
        echo "     uvicorn scheduler.simple_server:app --host 0.0.0.0 --port 8000"
    fi
    echo "  3. 在其他电脑上运行节点客户端"
    echo ""
    echo "🛠️  管理命令:"
    echo "  • 查看日志: sudo journalctl -u idle-scheduler -f"
    echo "  • 重启服务: sudo systemctl restart idle-scheduler"
    echo "  • 停止服务: sudo systemctl stop idle-scheduler"
    echo ""
    echo -e "${YELLOW}⚠️  注意: 确保防火墙开放端口8000${NC}"
    echo "  sudo ufw allow 8000/tcp  # Ubuntu"
    echo "  sudo firewall-cmd --add-port=8000/tcp --permanent  # CentOS"
    echo ""
}

# 主函数
main() {
    detect_os
    check_dependencies
    setup_project_dir
    setup_project_files
    install_python_deps
    configure_scheduler
    finish_installation
}

# 运行主函数
main "$@"

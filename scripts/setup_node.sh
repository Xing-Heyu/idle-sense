#!/bin/bash
# scripts/setup_node.sh
# 计算节点一键安装脚本

set -e

echo "🖥️  闲置计算加速器 - 计算节点安装脚本"
echo "========================================"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检测操作系统
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    else
        OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    fi
    echo "操作系统: $OS"
}

# 获取调度中心地址
get_scheduler_url() {
    DEFAULT_URL="http://localhost:8000"
    
    echo ""
    echo -e "${YELLOW}请输入调度中心地址${NC}"
    echo "示例:"
    echo "  • 本地测试: http://localhost:8000"
    echo "  • 局域网: http://192.168.1.100:8000"
    echo "  • 公网: https://your-domain.com"
    echo ""
    
    read -p "调度中心URL [$DEFAULT_URL]: " SCHEDULER_URL
    SCHEDULER_URL=${SCHEDULER_URL:-$DEFAULT_URL}
    
    # 验证URL格式
    if [[ ! $SCHEDULER_URL =~ ^https?:// ]]; then
        echo -e "${RED}错误: URL必须以 http:// 或 https:// 开头${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ 调度中心: $SCHEDULER_URL${NC}"
}

# 配置节点设置
configure_node() {
    echo ""
    echo -e "${YELLOW}配置节点设置${NC}"
    
    # 节点名称
    DEFAULT_NAME="$(hostname)-$(whoami)"
    read -p "节点名称 [$DEFAULT_NAME]: " NODE_NAME
    NODE_NAME=${NODE_NAME:-$DEFAULT_NAME}
    
    # 检测间隔
    read -p "闲置检测间隔(秒) [30]: " CHECK_INTERVAL
    CHECK_INTERVAL=${CHECK_INTERVAL:-30}
    
    # 闲置阈值
    read -p "闲置判定阈值(秒) [300]: " IDLE_THRESHOLD
    IDLE_THRESHOLD=${IDLE_THRESHOLD:-300}
    
    # 创建配置文件
    mkdir -p "$HOME/.idle-accelerator"
    
    cat > "$HOME/.idle-accelerator/config.yaml" << EOF
# 节点配置
node:
  scheduler_url: "$SCHEDULER_URL"
  node_name: "$NODE_NAME"
  
  idle_detection:
    check_interval: $CHECK_INTERVAL
    idle_threshold: $IDLE_THRESHOLD
    cpu_threshold: 30.0
    memory_threshold: 70.0
  
  security:
    max_task_time: 300
    max_memory_mb: 1024
    network_access: false
    auto_cleanup: true
    
  resources:
    max_cpu_cores: 2.0
    max_memory_mb: 4096
    reserve_cpu: 0.5
    reserve_memory_mb: 1024
EOF
    
    echo -e "${GREEN}✓ 配置文件已保存: ~/.idle-accelerator/config.yaml${NC}"
}

# 安装系统依赖（平台特定）
install_system_deps() {
    echo -e "${YELLOW}安装系统依赖...${NC}"
    
    case $OS in
        ubuntu|debian)
            sudo apt-get update
            sudo apt-get install -y python3-pip python3-venv procps lsof
            ;;
        centos|rhel|fedora)
            sudo yum install -y python3-pip python3-venv procps-ng lsof
            ;;
        macos)
            if ! command -v brew &> /dev/null; then
                echo -e "${YELLOW}安装Homebrew...${NC}"
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            fi
            brew install python3
            ;;
        *)
            echo -e "${YELLOW}请确保已安装Python3和pip${NC}"
            ;;
    esac
}

# 安装Python包
install_python_package() {
    echo -e "${YELLOW}安装Python包...${NC}"
    
    # 创建虚拟环境
    VENV_DIR="$HOME/.idle-accelerator/venv"
    
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
    fi
    
    # 激活虚拟环境
    source "$VENV_DIR/bin/activate"
    
    # 安装包
    pip install --upgrade pip
    
    # 安装idle-accelerator-node包（假设已发布）
    # pip install idle-accelerator-node
    
    # 临时：从当前目录安装
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        pip install psutil requests
    fi
    
    echo -e "${GREEN}✓ Python包安装完成${NC}"
}

# 设置自动启动
setup_autostart() {
    echo -e "${YELLOW}设置自动启动...${NC}"
    
    case $OS in
        linux)
            setup_systemd_service
            ;;
        macos)
            setup_launchd_service
            ;;
        *)
            echo -e "${YELLOW}请手动设置自动启动${NC}"
            create_manual_scripts
            ;;
    esac
}

# 设置systemd服务（Linux）
setup_systemd_service() {
    SERVICE_FILE="/etc/systemd/system/idle-node.service"
    
    if [ -f "$SERVICE_FILE" ]; then
        echo -e "${YELLOW}systemd服务已存在${NC}"
        return
    fi
    
    cat << EOF | sudo tee "$SERVICE_FILE" > /dev/null
[Unit]
Description=Idle Computing Node
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME
Environment="PATH=$HOME/.idle-accelerator/venv/bin"
ExecStart=$HOME/.idle-accelerator/venv/bin/python -m idle_sense.node.simple_client
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=idle-node

# 安全限制
NoNewPrivileges=true
ProtectSystem=strict
PrivateTmp=true
PrivateDevices=true
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    echo -e "${GREEN}✓ systemd服务已创建${NC}"
    
    read -p "启用并启动服务？(y/n) [y]: " ENABLE_SERVICE
    ENABLE_SERVICE=${ENABLE_SERVICE:-y}
    
    if [[ $ENABLE_SERVICE =~ ^[Yy]$ ]]; then
        sudo systemctl enable idle-node
        sudo systemctl start idle-node
        echo -e "${GREEN}✓ 服务已启用并启动${NC}"
    fi
}

# 设置launchd服务（macOS）
setup_launchd_service() {
    LAUNCHD_DIR="$HOME/Library/LaunchAgents"
    PLIST_FILE="$LAUNCHD_DIR/com.user.idle-node.plist"
    
    mkdir -p "$LAUNCHD_DIR"
    
    cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.idle-node</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>$HOME/.idle-accelerator/venv/bin/python</string>
        <string>-m</string>
        <string>idle_sense.node.simple_client</string>
    </array>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <true/>
    
    <key>StandardOutPath</key>
    <string>$HOME/.idle-accelerator/node.log</string>
    
    <key>StandardErrorPath</key>
    <string>$HOME/.idle-accelerator/node-error.log</string>
    
    <key>WorkingDirectory</key>
    <string>$HOME</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$HOME/.idle-accelerator/venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF
    
    # 加载服务
    launchctl load -w "$PLIST_FILE"
    echo -e "${GREEN}✓ launchd服务已创建${NC}"
}

# 创建手动启动脚本
create_manual_scripts() {
    SCRIPT_DIR="$HOME/.idle-accelerator/scripts"
    mkdir -p "$SCRIPT_DIR"
    
    # 启动脚本
    cat > "$SCRIPT_DIR/start-node.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate
python -m idle_sense.node.simple_client
EOF
    
    chmod +x "$SCRIPT_DIR/start-node.sh"
    
    # 停止脚本
    cat > "$SCRIPT_DIR/stop-node.sh" << 'EOF'
#!/bin/bash
pkill -f "idle_sense.node.simple_client"
EOF
    
    chmod +x "$SCRIPT_DIR/stop-node.sh"
    
    echo -e "${GREEN}✓ 手动脚本已创建:${NC}"
    echo "  启动: $SCRIPT_DIR/start-node.sh"
    echo "  停止: $SCRIPT_DIR/stop-node.sh"
}

# 测试连接
test_connection() {
    echo -e "${YELLOW}测试连接调度中心...${NC}"
    
    # 临时测试脚本
    cat > /tmp/test_connection.py << EOF
import requests
import sys

try:
    response = requests.get("$SCHEDULER_URL", timeout=5)
    if response.status_code == 200:
        print("✅ 连接调度中心成功")
        print(f"   服务: {response.json().get('service', 'Unknown')}")
        print(f"   状态: {response.json().get('status', 'Unknown')}")
        sys.exit(0)
    else:
        print(f"❌ 连接失败: HTTP {response.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"❌ 连接错误: {e}")
    sys.exit(1)
EOF
    
    source "$HOME/.idle-accelerator/venv/bin/activate"
    python /tmp/test_connection.py
    rm /tmp/test_connection.py
}

# 完成安装
finish_installation() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}🎉 计算节点安装完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "📋 节点信息:"
    echo "  • 节点名称: $NODE_NAME"
    echo "  • 调度中心: $SCHEDULER_URL"
    echo "  • 配置目录: ~/.idle-accelerator/"
    echo ""
    
    echo "🛠️  管理命令:"
    case $OS in
        linux)
            echo "  • 查看状态: sudo systemctl status idle-node"
            echo "  • 查看日志: sudo journalctl -u idle-node -f"
            echo "  • 重启节点: sudo systemctl restart idle-node"
            ;;
        macos)
            echo "  • 查看状态: launchctl list | grep idle-node"
            echo "  • 查看日志: tail -f ~/.idle-accelerator/node.log"
            echo "  • 重启节点: launchctl unload ~/Library/LaunchAgents/com.user.idle-node.plist; launchctl load ~/Library/LaunchAgents/com.user.idle-node.plist"
            ;;
        *)
            echo "  • 启动节点: ~/.idle-accelerator/scripts/start-node.sh"
            echo "  • 停止节点: ~/.idle-accelerator/scripts/stop-node.sh"
            ;;
    esac
    echo ""
    echo "📊 验证节点已注册:"
    echo "  curl $SCHEDULER_URL/nodes"
    echo ""
    echo -e "${YELLOW}⚠️  节点将在系统闲置时自动参与计算${NC}"
    echo ""
}

# 主函数
main() {
    detect_os
    get_scheduler_url
    configure_node
    install_system_deps
    install_python_package
    setup_autostart
    test_connection
    finish_installation
}

# 运行主函数
main "$@"

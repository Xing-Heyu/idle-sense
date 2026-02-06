📄 创建 USER_GUIDE.md（用户指南）
markdown
# 🧭 闲置计算加速器 - 用户指南

## 📋 快速开始

### 选项A：一键安装（推荐新手）
```bash
# 1. 下载项目
git clone https://github.com/你的用户名/idle-accelerator.git
cd idle-accelerator

# 2. 根据你的角色选择安装脚本
选项B：手动安装（高级用户）
参考 docs/DEPLOYMENT.md 进行详细配置。

🎯 三个用户角色对应三种安装方式
1. 🏢 调度中心管理员（运行任务分发中心）
bash
# 运行调度中心安装脚本
./scripts/setup_scheduler.sh

# 安装完成后访问：
# - 调度中心面板: http://你的IP:8000
# - API文档: http://你的IP:8000/docs
适用场景：

你想创建一个计算网络

你要管理任务分发

你需要监控所有计算节点

2. 🖥️ 计算节点提供者（贡献闲置算力）
bash
# 运行节点安装脚本
./scripts/setup_node.sh

# 脚本会询问：
# 1. 调度中心地址（例如: http://192.168.1.100:8000）
# 2. 节点名称（例如: 我的游戏本）
# 3. 闲置检测设置
适用场景：

你的电脑经常闲置

你想贡献算力帮助他人

你想参与分布式计算

3. 🚀 演示体验者（快速体验完整系统）
bash
# 需要先安装 Docker
# 然后运行演示部署脚本
./scripts/deploy_demo.sh

# 启动后访问：
# - 调度中心: http://localhost:8000
# - 网页控制台: http://localhost:8501
# - 监控面板: http://localhost:9090
适用场景：

你想快速体验系统

你要做演示或展示

你想了解系统架构

🔧 安装脚本详细说明
📡 scripts/setup_scheduler.sh（调度中心安装）
功能：

自动检测操作系统

安装Python和依赖

配置系统服务（systemd/launchd）

设置防火墙规则

创建配置文件

支持系统：

✅ Ubuntu/Debian (18.04+)

✅ CentOS/RHEL (7+)

✅ macOS (10.15+)

⚠️ Windows (建议使用WSL)

安装目录： ~/idle-accelerator/

🖥️ scripts/setup_node.sh（计算节点安装）
功能：

配置连接到调度中心

设置闲置检测参数

配置安全执行环境

设置开机自启

创建本地配置

配置存储： ~/.idle-accelerator/

🚀 scripts/deploy_demo.sh（演示环境）
功能：

使用Docker创建完整演示环境

包含：调度中心 + 网页界面 + 2个模拟节点

自动配置网络和端口

提供监控面板

要求： 已安装 Docker 和 docker-compose

✅ scripts/quick_test.py（快速测试）
功能：

测试调度中心连接

测试闲置检测功能

测试任务提交流程

生成测试报告

用法：

bash
python scripts/quick_test.py
# 或指定调度中心地址
python scripts/quick_test.py --scheduler http://192.168.1.100:8000
🖥️ 各操作系统具体步骤
Windows 用户
bash
# 推荐使用 WSL2 (Windows Subsystem for Linux)
# 1. 安装 WSL2: https://docs.microsoft.com/windows/wsl/install
# 2. 打开 Ubuntu 终端
# 3. 按照上面的 Linux 步骤操作

# 或使用 PowerShell（部分功能可能受限）
# 以管理员身份运行 PowerShell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
.\scripts\setup_scheduler.ps1  # 需要创建 PowerShell 版本
macOS 用户
bash
# 1. 确保已安装 Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. 运行安装脚本
./scripts/setup_scheduler.sh

# 3. 安装完成后，节点会作为后台服务运行
Linux 用户
bash
# Ubuntu/Debian
sudo apt update
./scripts/setup_scheduler.sh

# CentOS/RHEL/Fedora
sudo yum update
./scripts/setup_scheduler.sh
📊 安装后验证
验证调度中心
bash
# 检查服务状态
sudo systemctl status idle-scheduler  # Linux
launchctl list | grep idle-scheduler  # macOS

# 测试API
curl http://localhost:8000/health
验证计算节点
bash
# 检查服务状态
sudo systemctl status idle-node  # Linux
launchctl list | grep idle-node  # macOS

# 查看日志
tail -f ~/.idle-accelerator/node.log
验证完整系统
bash
# 运行全面测试
python scripts/quick_test.py --all

# 测试结果示例：
# ✅ 调度中心连接成功
# ✅ 闲置检测功能正常
# ✅ 任务提交和执行正常
# ✅ 网页界面可访问
🚨 常见问题
Q1: 安装脚本提示权限不足
bash
# 给脚本执行权限
chmod +x scripts/*.sh

# 以管理员身份运行（部分步骤需要）
sudo ./scripts/setup_scheduler.sh
Q2: 调度中心无法从外部访问
bash
# 检查防火墙
sudo ufw allow 8000/tcp  # Ubuntu
sudo firewall-cmd --add-port=8000/tcp --permanent  # CentOS

# 检查绑定地址
# 编辑 config/config.yaml，确保 host: "0.0.0.0"
Q3: 节点连接不上调度中心
bash
# 1. 检查网络连通性
ping 调度中心IP

# 2. 检查调度中心是否运行
curl http://调度中心IP:8000/

# 3. 检查节点配置
cat ~/.idle-accelerator/config.yaml
Q4: 任务执行失败
bash
# 查看调度中心日志
sudo journalctl -u idle-scheduler -f

# 查看节点日志
tail -f ~/.idle-accelerator/node.log

# 检查资源限制
# 编辑配置文件增加内存/时间限制
📞 获取帮助
查看详细文档
架构说明 - 系统架构图

部署指南 - 详细部署步骤

API参考 - 所有API接口

设计决策 - 设计理念

报告问题
检查 常见问题

查看日志文件

提交 Issue: https://github.com/你的用户名/idle-accelerator/issues

社区支持
📧 邮箱: 你的邮箱

💬 Discord/Slack: [链接]

🌐 项目主页: https://github.com/你的用户名/idle-accelerator

🔄 更新和维护
更新到新版本
bash
# 1. 进入项目目录
cd ~/idle-accelerator

# 2. 拉取最新代码
git pull origin main

# 3. 更新依赖
pip install -r requirements.txt --upgrade

# 4. 重启服务
sudo systemctl restart idle-scheduler
sudo systemctl restart idle-node
卸载系统
bash
# 停止服务
sudo systemctl stop idle-scheduler
sudo systemctl stop idle-node

# 禁用服务
sudo systemctl disable idle-scheduler
sudo systemctl disable idle-node

# 删除服务文件
sudo rm /etc/systemd/system/idle-scheduler.service
sudo rm /etc/systemd/system/idle-node.service

# 删除项目目录（可选）
rm -rf ~/idle-accelerator
rm -rf ~/.idle-accelerator
📜 许可证和贡献
本项目采用 MIT 许可证。欢迎贡献！

报告Bug: Issues页面

提交功能请求: Discussions

贡献代码: 提交Pull Request

开始使用：选择你的角色，运行对应的脚本吧！ 🚀

最后更新: 2024年1月
文档版本: 1.0

text

## 📁 **最终项目结构**
idle-accelerator/
├── USER_GUIDE.md # ✅ 新增：用户指南（放在根目录，最显眼）
├── scripts/ # 安装脚本
│ ├── setup_scheduler.sh
│ ├── setup_node.sh
│ ├── deploy_demo.sh
│ └── quick_test.py
├── idle_sense/ # 核心代码
├── scheduler/ # 核心代码
├── node/ # 核心代码
├── config/ # 配置
├── docs/ # 详细文档
│ ├── ARCHITECTURE.md
│ ├── DESIGN_DECISIONS.md
│ ├── API_REFERENCE.md
│ └── DEPLOYMENT.md
├── web_interface.py # 网页界面
├── requirements.txt # 依赖
└── README.md # 项目简介

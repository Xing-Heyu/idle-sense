# 🖥️ Idle-Sense: 对等个人中心 - 分布式闲置算力共享平台

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Version: v2.0.0](https://img.shields.io/badge/version-v2.0.0-green.svg)](https://github.com/Xing-Heyu/idle-sense)
[![Status: Beta](https://img.shields.io/badge/status-Beta%20阶段后期-orange.svg)](https://github.com/Xing-Heyu/idle-sense)

**让全球闲置算力不再浪费**

Idle-Sense 是一个分布式计算平台，采用"对等个人中心"架构，每个用户运行自己的完整栈，通过联邦模块互联，形成去中心化的算力联盟。

## ✨ 核心特性

- 🔍 **智能闲置检测** - 多维度检测（CPU/内存/用户活动/屏幕状态），确保不干扰正常使用
- 🛡️ **安全沙箱执行** - 多级隔离（进程/容器/VM/WASM），保护提供者安全
- ⚖️ **公平调度算法** - 基于贡献度的公平优先调度，防止饥饿
- 💰 **代币激励机制** - 贡献算力获得代币奖励，消费算力支付代币
- 🌐 **联邦网络** - 调度器互联，自动发现，任务共享
- 📊 **Web管理界面** - 直观的任务提交、监控和管理

## 🏗️ 架构说明

### 对等个人中心架构

```
用户 A 环境                           用户 B 环境
┌─────────────────────────┐          ┌─────────────────────────┐
│ Web UI ←→ 调度器 A       │←—P2P—→│ 调度器 B ←→ Web UI       │
│              ↑           │          │           ↑             │
│         本地节点 A        │          │      本地节点 B         │
│              ↑           │          │           ↑             │
│         (执行任务)        │          │      (执行任务)         │
└─────────────────────────┘          └─────────────────────────┘
```

### 联邦模块功能

| 功能 | 说明 |
|------|------|
| **发现** | 通过组播/DHT 发现其他调度器 |
| **握手** | 与其他调度器建立长连接 |
| **节点同步** | 广播本地节点列表 |
| **任务路由** | 本地无空闲节点时自动转发 |
| **结果回传** | 远程执行结果沿原路径返回 |

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/Xing-Heyu/idle-sense.git
cd idle-sense

# 安装依赖
pip install -r requirements.txt
```

### 启动

**方式一：一键启动（推荐）**

```bash
# Windows
.\start.bat

# 或直接运行 Python 脚本
python start.py
```

这会自动：
- 启动调度器、工作节点和 Web 界面
- 加载 Legacy 模块（健康检查、分布式锁、监控等）
- 实现零配置跨网络连接

**方式二：命令行启动**

```bash
# 完整模式
python start.py

# 仅调度器
python start.py --role scheduler

# 仅工作节点
python start.py --role worker --scheduler-url http://192.168.1.100:8000
```

**方式三：手动启动（Linux/macOS）**

```bash
python -m legacy.scheduler.simple_server  # 终端1：启动调度器
python -m legacy.node.simple_client --scheduler-url http://localhost:8000  # 终端2：启动节点
streamlit run src/presentation/streamlit/app.py  # 终端3：启动Web界面
```

### 验证

- Web界面：<http://localhost:8501>
- API文档：<http://localhost:8000/docs>
- 联邦状态：<http://localhost:8000/api/federation/stats>

## ⚙️ 环境变量

| 变量名 | 默认值 | 说明 |
|--------|-------|------|
| `ENABLE_FEDERATION` | `true` | 启用联邦模式 |
| `FEDERATION_PORT` | `8765` | 联邦通信端口 |
| `PORT` | `8000` | HTTP API端口 |
| `IDLESENSE_DATA_DIR` | `./data` | 数据存储根目录 |
| `IDLESENSE_DB_PATH` | `./data/idle_sense.db` | SQLite 数据库路径 |
| `STUN_SERVER` | `stun.l.google.com:19302` | STUN服务器地址 |
| `DHT_BOOTSTRAP` | `router.bittorrent.com:6881` | DHT引导节点 |

## 📖 文档

- [项目介绍](项目介绍文档.md) - 完整项目介绍与规划
- [快速入门指南](docs/QUICKSTART.md) - 5分钟快速上手
- [用户指南](USER_GUIDE.md) - 详细使用说明
- [API参考](docs/API_REFERENCE.md) - 完整API文档
- [架构设计](docs/ARCHITECTURE.md) - 系统架构说明
- [部署指南](部署指南_Deployment_Guide.md) - 生产环境部署
- [设计决策](docs/DESIGN_DECISIONS.md) - 关键设计选择
- [小白使用指南](超级小白保姆级使用指南.md) - 超详细新手教程

## 🗄️ 项目结构

```
idle-sense/
├── legacy/                    # 原始实现（向后兼容）
│   ├── idle_sense/           # 闲置检测库
│   ├── scheduler/            # 调度中心
│   │   └── p2p_federation.py # 联邦模块
│   ├── node/                 # 节点客户端
│   ├── demo/                 # 演示脚本
│   └── examples/             # 示例任务
├── src/                      # 新架构实现
│   ├── core/                 # 核心业务逻辑
│   │   ├── entities/         # 领域实体
│   │   ├── use_cases/        # 用例层
│   │   └── services/         # 服务层
│   ├── infrastructure/       # 基础设施层
│   │   ├── external/         # 外部服务客户端
│   │   └── repositories/     # 数据仓储
│   ├── presentation/         # 表现层
│   │   └── streamlit/        # Web界面
│   └── di/                   # 依赖注入
├── config/                   # 配置文件
├── docs/                     # 文档
├── tests/                    # 测试
└── scripts/                  # 工具脚本
```

## 🛡️ 安全沙箱支持

| 沙箱类型 | 隔离级别 | 平台支持 | 性能开销 |
|---------|---------|---------|---------|
| BasicSandbox | 进程级 | 全平台 | 最低 |
| DockerSandbox | 容器级 | 全平台 | 低 |
| GVisorSandbox | 系统调用 | Linux | 中 |
| FirecrackerSandbox | 微虚拟机 | Linux | 高 |
| WASMSandbox | 沙箱运行时 | 全平台 | 低 |

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 生成覆盖率报告
pytest --cov=legacy --cov=src --cov-report=html
```

## 🤝 贡献

我们欢迎所有形式的贡献！

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

详见 [贡献指南](CONTRIBUTING.md)。

## 📜 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🙏 致谢

- 所有贡献者和测试用户
- 开源社区的支持

## 📞 联系方式

- 项目主页: https://github.com/Xing-Heyu/idle-sense
- 问题反馈: https://github.com/Xing-Heyu/idle-sense/issues

---

**让每一份闲置算力都有价值** 💡

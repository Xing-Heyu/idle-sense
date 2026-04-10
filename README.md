# 🖥️ Idle-Sense: 分布式闲置算力共享平台

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Version: v2.0.0](https://img.shields.io/badge/version-v2.0.0-green.svg)](https://github.com/Xing-Heyu/idle-sense)
[![Status: Beta](https://img.shields.io/badge/status-Beta%20阶段后期-orange.svg)](https://github.com/Xing-Heyu/idle-sense)

**让全球闲置算力不再浪费**

Idle-Sense 是一个分布式计算平台，能够智能检测个人电脑的闲置状态，安全地利用闲置算力执行计算任务，并奖励贡献者。

## ✨ 核心特性

- 🔍 **智能闲置检测** - 多维度检测（CPU/内存/用户活动/屏幕状态），确保不干扰正常使用
- 🛡️ **安全沙箱执行** - 多级隔离（进程/容器/VM/WASM），保护提供者安全
- ⚖️ **公平调度算法** - 基于贡献度的公平优先调度，防止饥饿
- 💰 **代币激励机制** - 贡献算力获得代币奖励，消费算力支付代币
- 🌐 **P2P分布式网络** - 去中心化节点发现和任务分发
- 📊 **Web管理界面** - 直观的任务提交、监控和管理

## 🗄️ 数据持久化

| 组件 | 存储方式 | 状态 |
|------|---------|------|
| 调度器任务 | SQLite + 内存缓存 | ✅ 已实现 |
| 节点信息 | SQLite + 内存缓存 | ✅ 已实现 |
| 代币经济 | SQLite（原子事务） | ✅ 已实现 |
| 用户数据 | JSON 文件 | ✅ 已实现 |
| 会话管理 | 文件 / Redis | ✅ 已实现（默认文件） |

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/Xing-Heyu/idle-sense.git
cd idle-sense

# 安装依赖
pip install -r requirements.txt
```

> **首次运行**：系统会自动创建 `data/` 目录，用于存放 SQLite 数据库文件、用户数据及会话信息。无需手动初始化。

### 启动调度中心

```bash
python -m legacy.scheduler.simple_server
```

### 启动计算节点

```bash
python -m legacy.node.simple_client --scheduler http://localhost:8000
```

### 启动Web界面

```bash
streamlit run src/presentation/streamlit/app.py
```

访问 http://localhost:8501 打开Web管理界面。

## ⚙️ 环境变量

| 变量名 | 默认值 | 说明 |
|--------|-------|------|
| `IDLESENSE_DATA_DIR` | `./data` | 数据存储根目录 |
| `IDLESENSE_DB_PATH` | `./data/idle_sense.db` | SQLite 数据库路径 |
| `IDLESENSE_SESSION_BACKEND` | `file` | 会话后端：`file` 或 `redis` |
| `IDLESENSE_REDIS_URL` | - | Redis 连接 URL（仅 redis 后端时需要） |
| `IDLESENSE_CACHE_TTL` | `300` | 内存缓存过期时间（秒） |

## 📖 文档

- [项目介绍](项目介绍文档.md) - 完整项目介绍与规划
- [快速入门指南](docs/QUICKSTART.md) - 5分钟快速上手
- [用户指南](USER_GUIDE.md) - 详细使用说明
- [API参考](docs/API_REFERENCE.md) - 完整API文档
- [架构设计](docs/ARCHITECTURE.md) - 系统架构说明
- [部署指南](docs/DEPLOYMENT.md) - 生产环境部署
- [设计决策](docs/DESIGN_DECISIONS.md) - 关键设计选择

## 🏗️ 项目结构

```
idle-sense/
├── legacy/                    # 原始实现（向后兼容）
│   ├── idle_sense/           # 闲置检测库
│   ├── scheduler/            # 调度中心
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

## 🔧 命令行工具

```bash
# 检查调度器状态
python -m legacy.scheduler.cli status

# 列出所有节点
python -m legacy.node.cli list

# 提交任务
python -m legacy.task.cli submit --code "print('Hello')"

# 查询任务状态
python -m legacy.task.cli status --task-id <TASK_ID>
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

# 部署指南 | Deployment Guide

## ⚠️ 重要提示

**当前版本采用"对等个人中心"架构，每个用户运行自己的完整栈，通过联邦模块互联。**

---

## 🏠 本地运行（联邦模式）

### 快速安装

```powershell
git clone https://github.com/Xing-Heyu/idle-sense.git
cd idle-sense
pip install -r requirements.txt
```

### 启动服务

**方式一：一键启动（推荐）**

```powershell
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

```powershell
# 完整模式
python start.py

# 仅调度器
python start.py --role scheduler

# 仅工作节点
python start.py --role worker --scheduler-url http://192.168.1.100:8000
```

**方式三：手动启动**

```powershell
# 终端1：启动调度器
python -m legacy.scheduler.simple_server

# 终端2：启动节点
python -m legacy.node.simple_client --scheduler-url http://localhost:8000

# 终端3：启动Web界面
streamlit run src/presentation/streamlit/app.py
```

### 验证服务

- Web界面：<http://localhost:8501>
- API文档：<http://localhost:8000/docs>
- 联邦状态：<http://localhost:8000/api/federation/stats>
- 网络发现：<http://localhost:8000/api/federation/nodes>

### 网络发现时间

| 网络类型 | 发现时间 | 说明 |
|---------|---------|------|
| 局域网 | 5-10秒 | 组播发现，即时连接 |
| 广域网 | 20-60秒 | DHT发现 + STUN穿透 |
| 极端NAT | 1-2分钟 | TURN中继兜底 |

---

## 🌐 联邦网络配置

### 架构说明

```
用户 A 环境                           用户 B 环境
┌─────────────────────────┐          ┌─────────────────────────┐
│ Web UI ←→ 调度器 A       │←—P2P—→│ 调度器 B ←→ Web UI       │
│              ↑           │          │           ↑             │
│         本地节点 A        │          │      本地节点 B         │
└─────────────────────────┘          └─────────────────────────┘
```

### 局域网部署

1. **确保网络互通**：所有用户在同一局域网
2. **开放端口**：
   - HTTP端口：8000
   - 联邦端口：8765
3. **启动服务**：每个用户运行 `start.bat`
4. **自动发现**：调度器通过组播自动发现

### 公网部署

需要配置：
- 公网IP或域名
- 防火墙开放 8000 和 8765 端口
- NAT穿透（如需要）

---

## 🐳 Docker 部署

### Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000 8765 8501

ENV ENABLE_FEDERATION=true
ENV FEDERATION_PORT=8765
ENV PORT=8000

# 广域网自动连接入口
CMD ["python", "start.py"]
```

### docker-compose.yml

```yaml
version: '3.8'
services:
  idle-sense:
    build: .
    ports:
      - "8000:8000"    # HTTP API
      - "8765:8765"    # Federation
      - "8501:8501"    # Web UI
    environment:
      - ENABLE_FEDERATION=true
      - FEDERATION_PORT=8765
      - PORT=8000
    volumes:
      - ./data:/app/data
    network_mode: host  # 推荐使用 host 模式以支持组播和 P2P
```

### 启动

```bash
docker-compose up -d
```

### 注意事项

Docker 部署时：
- 使用 `network_mode: host` 以支持组播和 P2P 通信
- 如果无法使用 host 模式，需要额外配置端口映射和 NAT 穿透

---

## ⚙️ 环境变量

| 变量名 | 默认值 | 说明 |
|--------|-------|------|
| `ENABLE_FEDERATION` | `true` | 启用联邦模式 |
| `FEDERATION_PORT` | `8765` | 联邦通信端口 |
| `PORT` | `8000` | HTTP API端口 |
| `IDLESENSE_DATA_DIR` | `./data` | 数据存储目录 |
| `IDLESENSE_DB_PATH` | `./data/idle_sense.db` | SQLite数据库路径 |
| `STUN_SERVER` | `stun.l.google.com:19302` | STUN服务器地址 |
| `DHT_BOOTSTRAP` | `router.bittorrent.com:6881` | DHT引导节点 |

---

## 🔒 安全要求

### 本地/局域网部署

- [x] 进程级沙箱隔离
- [x] 代码执行超时控制
- [x] 资源使用限制

### 公网部署（额外要求）

- [ ] HTTPS 加密传输
- [ ] JWT 令牌认证
- [ ] SQL 注入防护
- [ ] XSS/CSRF 防护
- [ ] 输入验证
- [ ] 访问控制
- [ ] 审计日志

---

## 📊 监控与维护

### 健康检查

```bash
# 检查调度器状态
curl http://localhost:8000/health

# 详细健康检查（Legacy 模块）
curl http://localhost:8000/api/health/detailed

# Prometheus 指标
curl http://localhost:8000/metrics

# Legacy 模块状态
curl http://localhost:8000/api/legacy/status

# 检查联邦状态
curl http://localhost:8000/api/federation/stats

# 检查节点状态
curl http://localhost:8000/api/federation/nodes
```

### 日志查看

日志输出到标准输出，可通过以下方式查看：

```bash
# Docker
docker logs <container_id>

# 直接运行
# 查看终端输出
```

### 网络诊断

```bash
# 检查 NAT 类型
python -c "from legacy.p2p_network.stun import STUNClient; import asyncio; print(asyncio.run(STUNClient().discover_nat_type()))"

# 检查公网 IP
curl https://api.ipify.org

# 测试 DHT 连接
python -c "import socket; s=socket.socket(); s.settimeout(5); s.connect(('router.bittorrent.com', 6881)); print('DHT OK')"
```

---

## 📚 参考资源

- [FastAPI 部署指南](https://fastapi.tiangolo.com/deployment/)
- [Docker 部署最佳实践](https://docs.docker.com/develop/dev-best-practices/)
- [Web 应用安全指南](https://owasp.org/)

---

**最后更新**: 2025-04-11

# 部署指南 | Deployment Guide

## ⚠️ 重要提示

**当前版本是本地运行版本，网上部署需要额外配置！**

---

## 🏠 本地运行

### 快速安装

```powershell
git clone https://github.com/Xing-Heyu/idle-sense.git
cd idle-sense
pip install -r requirements.txt
```

### 启动服务

```powershell
# 启动调度中心
python -m legacy.scheduler.simple_server

# 启动计算节点（另一个终端）
python -m legacy.node.simple_client --scheduler http://localhost:8000

# 启动Web界面（第三个终端）
streamlit run src/presentation/streamlit/app.py
```

详细使用说明请查看 [USER_GUIDE.md](USER_GUIDE.md)

---

## 🌐 网上部署

### 需要修改的内容

| 项目 | 本地版本 | 网上部署 |
|-----|---------|---------|
| 调度器URL | `localhost:8000` | `your-domain.com:8000` |
| 用户存储 | 本地 JSON | 数据库 (PostgreSQL) |
| 认证方式 | 无 | JWT + OAuth2 |
| 传输协议 | HTTP | HTTPS |

### Docker 部署

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "-m", "legacy.scheduler.simple_server"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  scheduler:
    build: .
    ports:
      - "8000:8000"
  redis:
    image: redis:alpine
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: idlesense
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
```

### 安全要求

- [ ] HTTPS 加密传输
- [ ] JWT 令牌认证
- [ ] SQL 注入防护
- [ ] XSS/CSRF 防护
- [ ] 输入验证
- [ ] 访问控制
- [ ] 审计日志

---

## 📚 参考资源

- [FastAPI 部署指南](https://fastapi.tiangolo.com/deployment/)
- [Docker 部署最佳实践](https://docs.docker.com/develop/dev-best-practices/)
- [Web 应用安全指南](https://owasp.org/)

---

**最后更新**: 2026-03-28

# 部署指南 | Deployment Guide

## ⚠️ 重要提示 | IMPORTANT NOTICE

**当前版本是本地运行版本，不是网上可运行版本！**
**This is a LOCAL RUN version, NOT a web-deployable version!**

即使本地运行也需要使用虚拟环境！
Even for local running, you need to use a virtual environment!

---

## 📋 目录 | Table of Contents

1. [本地运行环境设置 | Local Environment Setup](#本地运行环境设置--local-environment-setup)
2. [网上部署指南 | Web Deployment Guide](#网上部署指南--web-deployment-guide)
3. [架构差异 | Architecture Differences](#架构差异--architecture-differences)
4. [安全注意事项 | Security Considerations](#安全注意事项--security-considerations)

---

## 🏠 本地运行环境设置 | Local Environment Setup

### 前置要求 | Prerequisites

- Python 3.8 或更高版本 | Python 3.8 or higher
- pip 包管理器 | pip package manager
- Git | Git

### 安装步骤 | Installation Steps

1. **克隆项目 | Clone the repository**
   ```bash
   git clone https://github.com/your-repo/idle-sense.git
   cd idle-sense
   ```

2. **创建虚拟环境 | Create virtual environment**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate
   
   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **安装依赖 | Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **启动调度中心 | Start scheduler**
   ```bash
   cd scheduler
   python simple_server.py
   ```

5. **启动Web界面 | Start web interface**
   ```bash
   # 在新终端中 | In new terminal
   cd idle-sense
   streamlit run web_interface.py --server.port 8501
   ```

6. **访问应用 | Access application**
   - 打开浏览器访问 | Open browser and visit: http://localhost:8501

---

## 🌐 网上部署指南 | Web Deployment Guide

### ⚠️ 重要警告 | CRITICAL WARNING

**当前代码不能直接用于网上部署！**
**Current code CANNOT be directly deployed to the web!**

需要进行以下重大修改：

### 1. 网络配置 | Network Configuration

#### 修改调度中心URL | Modify Scheduler URL

**当前 | Current:**
```python
SCHEDULER_URL = "http://localhost:8000"
```

**网上部署需要 | Web deployment needs:**
```python
import os
SCHEDULER_URL = os.getenv("SCHEDULER_URL", "https://your-domain.com:8000")
```

### 2. 用户认证系统 | User Authentication System

#### 当前本地存储 | Current Local Storage
```python
# 用户数据存储在本地JSON文件
users_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_users")
```

#### 网上部署需要 | Web Deployment Needs
- 数据库存储（PostgreSQL/MySQL）
- Redis会话管理
- JWT令牌认证
- OAuth2集成

### 3. 安全性增强 | Security Enhancement

#### HTTPS配置 | HTTPS Configuration
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### API安全 | API Security
```python
# 添加API密钥认证
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_token(token: str = Depends(security)):
    # 验证令牌逻辑
    pass
```

### 4. 容器化部署 | Containerized Deployment

#### Dockerfile示例 | Dockerfile Example
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8501

# 启动命令
CMD ["streamlit", "run", "web_interface.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

#### docker-compose.yml示例
```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8501:8501"
    environment:
      - SCHEDULER_URL=http://scheduler:8000
    depends_on:
      - scheduler
      - redis
      - db

  scheduler:
    build: ./scheduler
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/idlesense
    depends_on:
      - db

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"

  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=idlesense
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### 5. 数据持久化 | Data Persistence

#### 数据库模型示例 | Database Model Example
```python
# models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
```

### 6. 监控和日志 | Monitoring and Logging

#### 日志配置 | Logging Configuration
```python
import logging
from logging.handlers import RotatingFileHandler

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('logs/app.log', maxBytes=10485760, backupCount=5),
        logging.StreamHandler()
    ]
)
```

---

## 🏗️ 架构差异 | Architecture Differences

### 本地版本架构 | Local Version Architecture
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Web界面     │    │ 调度中心     │    │ 节点客户端   │
│ (Streamlit) │◄──►│ (FastAPI)   │◄──►│ (Python)    │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                          │
                  ┌─────────────┐
                  │ 本地JSON存储  │
                  │ 本地文件系统  │
                  └─────────────┘
```

### 网上部署架构 | Web Deployment Architecture
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ 负载均衡器   │    │ Web界面     │    │ 调度中心     │
│ (Nginx)     │◄──►│ (Streamlit) │◄──►│ (FastAPI)   │
└─────────────┘    └─────────────┘    └─────────────┘
                          │                   │
                          ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐
                   │ Redis缓存    │    │ 数据库       │
                   │ 会话管理     │    │ PostgreSQL  │
                   └─────────────┘    └─────────────┘
                          │                   │
                          ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐
                   │ 对象存储     │    │ 监控系统     │
                   │ 文件存储     │    │ 日志系统     │
                   └─────────────┘    └─────────────┘
```

---

## 🔒 安全注意事项 | Security Considerations

### 本地版本安全风险 | Local Version Security Risks
- 无认证机制 | No authentication
- 明文数据传输 | Plain text data transmission
- 本地文件系统访问 | Local file system access
- 无输入验证 | No input validation

### 网上部署安全要求 | Web Deployment Security Requirements
- HTTPS加密传输 | HTTPS encrypted transmission
- JWT令牌认证 | JWT token authentication
- SQL注入防护 | SQL injection protection
- XSS防护 | XSS protection
- CSRF防护 | CSRF protection
- 输入验证和清理 | Input validation and sanitization
- 访问控制 | Access control
- 审计日志 | Audit logging

---

## 📚 参考资源 | References

- [Streamlit部署文档](https://docs.streamlit.io/knowledge-base/tutorials/deploy)
- [FastAPI部署指南](https://fastapi.tiangolo.com/deployment/)
- [Docker部署最佳实践](https://docs.docker.com/develop/dev-best-practices/)
- [Web应用安全指南](https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/)

---

## 🤝 贡献指南 | Contributing

欢迎提交PR来改进网上部署支持！
Welcome to submit PRs to improve web deployment support!

---

## 📄 许可证 | License

本项目采用MIT许可证 | This project is licensed under the MIT License.
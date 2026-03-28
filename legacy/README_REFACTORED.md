# 闲置计算加速器 - 重构版

> ⚠️ **注意**: 此重构计划已完成。新架构已迁移到 `src/` 目录。

## 当前状态

✅ **重构已完成** - 2026-03-28

新架构位于 `src/` 目录，遵循 Clean Architecture 原则。

## 新架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│                  (Streamlit UI / CLI)                        │
├─────────────────────────────────────────────────────────────┤
│                    Application Layer                         │
│                   (Use Cases / DTOs)                        │
├─────────────────────────────────────────────────────────────┤
│                      Domain Layer                            │
│               (Entities / Interfaces)                        │
├─────────────────────────────────────────────────────────────┤
│                   Infrastructure Layer                      │
│          (Repositories / Services / Utils)                   │
└─────────────────────────────────────────────────────────────┘
```

## 当前项目结构

```
idle-sense/
├── src/                          # 新架构源代码
│   ├── core/                     # 核心业务层
│   │   ├── entities/             # 实体
│   │   ├── interfaces/           # 接口定义
│   │   ├── services/             # 业务服务
│   │   └── use_cases/            # 用例
│   ├── infrastructure/           # 基础设施层
│   │   ├── external/             # 外部服务
│   │   └── repositories/         # 仓储实现
│   ├── presentation/             # 表示层
│   │   └── streamlit/            # Web界面
│   └── di/                       # 依赖注入
├── legacy/                       # 遗留代码（兼容层）
├── config/                       # 配置管理
├── tests/                        # 测试
└── docs/                         # 文档
```

## 快速开始

### 运行新版界面

```bash
streamlit run src/presentation/streamlit/app.py
```

### 运行调度中心

```bash
python -m legacy.scheduler.simple_server
```

### 运行计算节点

```bash
python -m legacy.node.simple_client --scheduler http://localhost:8000
```

## 测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 查看覆盖率
pytest --cov=src --cov=legacy
```

## 重构成果

| 指标 | 重构前 | 重构后 | 改进 |
|-----|-------|-------|-----|
| 单文件行数 | 1973行 | ~200行 | -90% |
| 测试覆盖率 | ~0% | 99.7% | +99.7% |
| 单元测试数 | 0 | 593 | +593 |
| 代码可维护性 | 低 | 高 | 显著提升 |

## 相关文档

- [架构文档](../docs/ARCHITECTURE.md)
- [API参考](../docs/API_REFERENCE.md)
- [迁移计划](../.trae/documents/迁移计划-web_interface剩余功能.md)

---

**最后更新**: 2026-03-28

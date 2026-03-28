# 迁移计划：web_interface.py 剩余功能到新架构

## 概述

本计划将 `web_interface.py` 中剩余的功能迁移到符合 Clean Architecture 的新架构中，消除上帝类问题，统一代码风格。

## 当前状态分析

### 已完成迁移的功能

| 功能 | 原位置 | 新位置 | 状态 |
|------|--------|--------|------|
| 用户管理 | UserManager 类 | RegisterUseCase, LoginUseCase | ✅ 完成 |
| 权限管理 | PermissionManager 类 | PermissionService | ✅ 完成 |
| 文件夹管理 | FolderManager 类 | CreateFoldersUseCase, FolderService | ✅ 完成 |
| API客户端 | safe_api_call + 直接调用 | SchedulerClient | ✅ 完成 |
| 认证页面 | 登录/注册UI | auth_page.py | ✅ 完成 |
| 任务提交页面 | 分布式任务UI | task_submission_page.py | ✅ 完成 |
| 任务监控页面 | 监控UI | task_monitor_page.py | ✅ 完成 |
| 节点管理页面 | 节点UI | node_management_page.py | ✅ 完成 |
| 系统统计页面 | 统计UI | system_stats_page.py | ✅ 完成 |
| 任务结果页面 | 结果UI | task_results_page.py | ✅ 完成 |
| 侧边栏功能 | 侧边栏UI | sidebar.py | ✅ 完成 |
| 会话管理 | 持久化登录 | session_manager.py | ✅ 完成 |

### 迁移状态

| 功能 | 原位置 | 行数 | 复杂度 | 状态 |
|------|--------|------|--------|------|
| 分布式任务功能 | 第668-726行 | ~60行 | 中 | ✅ 已迁移 |
| 任务提交页面（分布式） | 第977-1174行 | ~200行 | 高 | ✅ 已迁移 |
| 任务监控页面 | 第1235-1416行 | ~180行 | 高 | ✅ 已迁移 |
| 节点管理页面 | 第1418-1492行 | ~75行 | 中 | ✅ 已迁移 |
| 系统统计页面 | 第1494-1643行 | ~150行 | 高 | ✅ 已迁移 |
| 任务结果页面 | 第1644-1711行 | ~70行 | 中 | ✅ 已迁移 |
| 侧边栏功能 | 第774-952行 | ~180行 | 中 | ✅ 已迁移 |
| 持久化登录恢复 | 第61-87行 | ~27行 | 低 | ✅ 已迁移 |

## 迁移计划（已完成）

### 阶段1：完善分布式任务支持 ✅

**目标**：完善 DistributedTaskClient 和相关页面

#### 1.1 更新依赖注入容器

**文件**：`src/di/container.py`

**修改内容**：
- 添加 DistributedTaskClient 的依赖注入
- 处理分布式任务模块不可用的情况

#### 1.2 完善任务提交页面

**文件**：`src/presentation/streamlit/views/task_submission_page.py`

**修改内容**：
- 添加分布式任务提交功能
- 添加数据输入方式选择（手动输入/文件上传）
- 添加自定义任务代码编辑器

**新增功能**：
- 任务模板选择
- 分片大小配置
- 最大并行节点数配置
- 数据类型选择（数字列表/文本列表/键值对）
- 文件上传支持

---

### 阶段2：完善任务监控页面 ✅

**目标**：添加任务删除、状态查看等完整功能

#### 2.1 更新任务监控页面

**文件**：`src/presentation/streamlit/views/task_monitor_page.py`

**修改内容**：
- 添加任务类型筛选（所有任务/单节点任务/分布式任务）
- 添加任务删除功能
- 添加任务实时状态查看
- 添加分布式任务进度显示

**新增功能**：
- 任务状态实时刷新
- 任务删除确认
- 任务详情展开
- 执行时间显示

---

### 阶段3：完善节点管理页面 ✅

**目标**：添加节点激活、停止、状态查看功能

#### 3.1 更新节点管理页面

**文件**：`src/presentation/streamlit/views/node_management_page.py`

**修改内容**：
- 添加节点激活功能
- 添加节点停止功能
- 添加节点列表显示
- 添加节点详情查看

**新增功能**：
- 节点状态检查
- 节点资源显示
- 节点所有者显示

---

### 阶段4：完善系统统计页面 ✅

**目标**：添加完整的统计图表和数据展示

#### 4.1 更新系统统计页面

**文件**：`src/presentation/streamlit/views/system_stats_page.py`

**修改内容**：
- 添加任务统计指标
- 添加节点统计指标
- 添加性能图表（Plotly）
- 添加用户任务结果展示

**新增功能**：
- 任务状态饼图
- 调度器统计柱状图
- 计算时数统计
- 原始数据查看

---

### 阶段5：完善任务结果页面 ✅

**目标**：添加任务结果搜索、下载功能

#### 5.1 更新任务结果页面

**文件**：`src/presentation/streamlit/views/task_results_page.py`

**修改内容**：
- 添加任务搜索功能
- 添加结果下载功能
- 添加分页显示
- 添加执行详情展示

**新增功能**：
- 任务ID/内容搜索
- 结果文件下载
- 显示数量控制
- 执行节点和时间显示

---

### 阶段6：完善侧边栏功能 ✅

**目标**：将侧边栏功能迁移到新架构

#### 6.1 创建侧边栏组件

**文件**：`src/presentation/streamlit/components/sidebar.py`

**修改内容**：
- 创建独立的侧边栏渲染函数
- 使用 SchedulerClient 替代直接 API 调用
- 使用 LoginUseCase 替代直接用户管理

**新增功能**：
- 调试模式切换
- 系统状态显示
- 用户状态管理
- 节点激活/停止
- 资源分配滑块

---

### 阶段7：添加持久化登录恢复 ✅

**目标**：将 localStorage 登录恢复功能迁移到新架构

#### 7.1 创建会话管理模块

**文件**：`src/presentation/streamlit/utils/session_manager.py`

**修改内容**：
- 创建会话管理工具类
- 处理 localStorage 恢复逻辑
- 处理 URL 参数恢复

**新增功能**：
- 会话持久化
- 会话恢复
- 会话清理

---

### 阶段8：更新主应用入口 ✅

**目标**：整合所有新组件到主应用

#### 8.1 更新主应用

**文件**：`src/presentation/streamlit/app.py`

**修改内容**：
- 使用新的侧边栏组件
- 使用新的会话管理
- 整合所有页面

**新增功能**：
- 统一的页面配置
- 统一的样式管理
- 统一的会话初始化

---

### 阶段9：创建迁移入口 ✅

**目标**：创建新的应用入口，替代 web_interface.py

#### 9.1 创建新入口文件

**文件**：`src/presentation/streamlit/app.py`

**代码示例**：

```python
"""
闲置计算加速器 - 新版Web界面
使用 Clean Architecture 架构
"""

from src.presentation.streamlit.app import main

if __name__ == "__main__":
    main()
```

---

## 文件变更清单

### 新增文件

| 文件路径 | 说明 |
|----------|------|
| `src/presentation/streamlit/components/sidebar.py` | 侧边栏组件 |
| `src/presentation/streamlit/utils/session_manager.py` | 会话管理工具 |
| `src/presentation/streamlit/views/auth_page.py` | 认证页面 |
| `src/presentation/streamlit/views/task_submission_page.py` | 任务提交页面 |
| `src/presentation/streamlit/views/task_monitor_page.py` | 任务监控页面 |
| `src/presentation/streamlit/views/node_management_page.py` | 节点管理页面 |
| `src/presentation/streamlit/views/system_stats_page.py` | 系统统计页面 |
| `src/presentation/streamlit/views/task_results_page.py` | 任务结果页面 |

### 修改文件

| 文件路径 | 修改内容 |
|----------|----------|
| `src/di/container.py` | 添加 DistributedTaskClient 依赖注入 |
| `src/presentation/streamlit/app.py` | 整合所有组件 |

### 废弃文件

| 文件路径 | 说明 |
|----------|------|
| `web_interface.py` | 旧版上帝类文件（已标记废弃） |

---

## 测试计划

### 单元测试

- [x] DistributedTaskClient 测试
- [x] SessionManager 测试
- [x] 各页面渲染函数测试

### 集成测试

- [x] 任务提交流程测试
- [x] 任务监控流程测试
- [x] 节点管理流程测试
- [x] 用户登录/注册流程测试

### 端到端测试

- [x] 完整用户流程测试
- [x] 分布式任务流程测试

---

## 风险评估

| 风险 | 影响 | 缓解措施 | 状态 |
|------|------|----------|------|
| 分布式任务模块不可用 | 中 | 使用 try-except 处理，提供降级方案 | ✅ 已解决 |
| 旧代码依赖 | 高 | 保持向后兼容，逐步迁移 | ✅ 已解决 |
| 测试覆盖不足 | 中 | 为新代码添加单元测试 | ✅ 已解决 |

---

## 时间估算

| 阶段 | 预计时间 | 实际时间 | 状态 |
|------|----------|----------|------|
| 阶段1：分布式任务支持 | 1小时 | 1小时 | ✅ 完成 |
| 阶段2：任务监控页面 | 1小时 | 1小时 | ✅ 完成 |
| 阶段3：节点管理页面 | 30分钟 | 30分钟 | ✅ 完成 |
| 阶段4：系统统计页面 | 1小时 | 1小时 | ✅ 完成 |
| 阶段5：任务结果页面 | 30分钟 | 30分钟 | ✅ 完成 |
| 阶段6：侧边栏功能 | 1小时 | 1小时 | ✅ 完成 |
| 阶段7：持久化登录 | 30分钟 | 30分钟 | ✅ 完成 |
| 阶段8：更新主应用 | 30分钟 | 30分钟 | ✅ 完成 |
| 阶段9：创建入口 | 15分钟 | 15分钟 | ✅ 完成 |
| 测试和验证 | 1小时 | 1小时 | ✅ 完成 |
| **总计** | **约7小时** | **约7小时** | ✅ 完成 |

---

## 验收标准

1. ✅ 所有页面功能与原 `web_interface.py` 一致
2. ✅ 代码符合 Clean Architecture 原则
3. ✅ 所有单元测试通过
4. ✅ 无 ruff 代码质量警告
5. ✅ 用户可以正常使用所有功能

---

**最后更新**: 2026-03-28

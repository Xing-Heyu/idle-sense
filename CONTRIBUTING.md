# 贡献指南

感谢您有兴趣为 Idle-Sense 做出贡献！本文档将帮助您了解如何参与项目开发。

## 目录

- [行为准则](#行为准则)
- [如何贡献](#如何贡献)
- [开发环境设置](#开发环境设置)
- [代码规范](#代码规范)
- [提交规范](#提交规范)
- [Pull Request 流程](#pull-request-流程)
- [问题报告](#问题报告)
- [功能请求](#功能请求)

---

## 行为准则

### 我们的承诺

为了营造一个开放和友好的环境，我们承诺：

- 尊重所有贡献者
- 接受建设性批评
- 关注对社区最有利的事情
- 对其他社区成员表示同理心

### 不可接受的行为

- 使用性化的语言或图像
- 捣乱、侮辱/贬损评论
- 公开或私下的骚扰
- 未经许可发布他人私人信息
- 其他不道德或不专业的行为

---

## 如何贡献

### 贡献方式

1. **报告Bug** - 提交详细的问题报告
2. **建议功能** - 提出新功能想法
3. **改进文档** - 修复错误或添加说明
4. **提交代码** - 修复Bug或实现新功能
5. **代码审查** - 帮助审查Pull Request

### 开始之前

1. 查看 [Issues](https://github.com/Xing-Heyu/idle-sense/issues) 了解当前任务
2. 对于重大更改，先开Issue讨论
3. Fork仓库并创建功能分支

---

## 开发环境设置

### 1. Fork并克隆

```bash
# Fork后克隆您的仓库
git clone https://github.com/YOUR_USERNAME/idle-sense.git
cd idle-sense
```

### 2. 创建虚拟环境

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. 安装开发依赖

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 如果存在
```

### 4. 配置Git

```bash
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

### 5. 创建功能分支

```bash
git checkout -b feature/your-feature-name
```

---

## 代码规范

### Python代码风格

我们遵循 [PEP 8](https://pep8.org/) 规范，并使用以下工具：

```bash
# 代码格式化
black .

# 代码检查
flake8 .

# 类型检查
mypy .
```

### 代码规范要点

1. **命名规范**
   - 类名: `PascalCase`
   - 函数/方法: `snake_case`
   - 常量: `UPPER_SNAKE_CASE`
   - 私有属性: `_leading_underscore`

2. **文档字符串**
   ```python
   def calculate_priority(node: NodeInfo) -> float:
       """
       计算节点优先级。
       
       Args:
           node: 节点信息对象
           
       Returns:
           优先级分数（越低优先级越高）
       """
       pass
   ```

3. **类型注解**
   ```python
   from typing import Optional, List
   
   def process_tasks(tasks: List[Task]) -> Optional[Result]:
       pass
   ```

4. **导入顺序**
   ```python
   # 标准库
   import os
   import sys
   
   # 第三方库
   import numpy as np
   import requests
   
   # 本地模块
   from legacy.scheduler import Scheduler
   from src.core.entities import Task
   ```

### 测试规范

1. **测试文件命名**: `test_<module_name>.py`
2. **测试类命名**: `Test<FeatureName>`
3. **测试方法命名**: `test_<scenario>_<expected_result>`

```python
class TestScheduler:
    def test_submit_task_returns_task_id(self):
        """测试提交任务返回任务ID"""
        scheduler = Scheduler()
        task_id = scheduler.submit_task("print('hello')")
        assert task_id is not None
```

---

## 提交规范

### 提交消息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type类型

- `feat`: 新功能
- `fix`: Bug修复
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具相关

### 示例

```
feat(scheduler): 添加任务优先级调度算法

实现了基于贡献度的公平优先调度算法：
- 等待时间权重60%
- 贡献度权重30%
- 新人加成权重10%

Closes #123
```

---

## Pull Request 流程

### 1. 确保代码质量

```bash
# 运行测试
pytest

# 代码格式化
black .

# 代码检查
flake8 .

# 类型检查
mypy .
```

### 2. 提交Pull Request

1. 推送到您的Fork
   ```bash
   git push origin feature/your-feature-name
   ```

2. 在GitHub上创建Pull Request

3. 填写PR模板：
   - 描述更改内容
   - 关联相关Issue
   - 说明测试方法

### 3. 代码审查

- 响应审查意见
- 及时更新代码
- 保持讨论专业和友好

### 4. 合并要求

- [ ] 所有测试通过
- [ ] 代码覆盖率不降低
- [ ] 代码风格符合规范
- [ ] 文档已更新
- [ ] 至少一位审查者批准

---

## 问题报告

### Bug报告模板

```markdown
**描述**
清晰简洁地描述Bug。

**复现步骤**
1. 执行 '...'
2. 点击 '...'
3. 滚动到 '...'
4. 看到错误

**预期行为**
描述您期望发生的事情。

**实际行为**
描述实际发生的事情。

**环境**
- OS: [例如 Windows 11]
- Python版本: [例如 3.11.0]
- 项目版本: [例如 1.0.0]

**附加信息**
截图、日志等。
```

---

## 功能请求

### 功能请求模板

```markdown
**功能描述**
清晰简洁地描述您想要的功能。

**问题背景**
描述这个功能解决什么问题。

**建议方案**
描述您建议的解决方案。

**替代方案**
描述您考虑过的其他方案。

**附加信息**
任何其他相关信息或截图。
```

---

## 项目结构

```
idle-sense/
├── legacy/           # 原始实现
├── src/              # 新架构
│   ├── core/         # 核心业务逻辑
│   ├── infrastructure/  # 基础设施
│   └── presentation/    # 表现层
├── tests/            # 测试
├── docs/             # 文档
└── config/           # 配置
```

---

## 获取帮助

- **GitHub Issues**: 提问和讨论
- **Pull Request**: 代码审查和讨论
- **文档**: 查阅项目文档

---

## 许可证

通过贡献代码，您同意您的贡献将根据项目的MIT许可证进行许可。

---

**感谢您的贡献！** 🎉

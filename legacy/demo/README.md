# 演示脚本集合

这个目录包含各种演示脚本，用于展示闲置计算加速器的完整功能。

## 可用演示

### 1. 单机演示 (`demo_single_machine.py`)

**目的**: 在一台电脑上展示完整流程

**功能**:
- 自动启动调度中心
- 启动计算节点
- 提交演示任务
- 监控任务执行
- 显示系统状态

```bash
python legacy/demo/demo_single_machine.py
```

### 2. Web界面演示 (`demo_web_interface.py`)

**目的**: 展示Web管理界面功能

**功能**:
- 启动Streamlit Web界面
- 展示用户注册登录
- 展示任务提交
- 展示任务监控
- 展示节点管理

```bash
python legacy/demo/demo_web_interface.py
```

### 3. 局域网演示 (`demo_local_network.py`)

**目的**: 展示多机协作能力

**功能**:
- 调度器节点启动
- 多个计算节点连接
- 分布式任务执行
- 结果汇总展示

```bash
python legacy/demo/demo_local_network.py
```

## 演示场景

### 场景1: 快速体验

```bash
# 最简单的单机演示
python legacy/demo/demo_single_machine.py
```

### 场景2: 完整展示

```bash
# 1. 启动单机演示（基础功能）
python legacy/demo/demo_single_machine.py

# 2. 展示网页界面（用户体验）
python legacy/demo/demo_web_interface.py

# 3. 如果有多个电脑，展示分布式计算
python legacy/demo/demo_local_network.py
```

### 场景3: 教学演示

```bash
# 分步骤展示
# 步骤1: 启动调度中心
python -m legacy.scheduler.simple_server

# 步骤2: 启动节点（在另一个终端）
python -m legacy.node.simple_client --scheduler http://localhost:8000

# 步骤3: 运行网页界面（第三个终端）
streamlit run src/presentation/streamlit/app.py

# 步骤4: 运行演示任务
python legacy/demo/demo_single_machine.py
```

## 创建自定义演示

参考现有演示创建新演示：

```python
# new_demo.py
from legacy.demo import demo_base

class CustomDemo(demo_base.BaseDemo):
    def run(self):
        # 自定义演示逻辑
        pass

if __name__ == "__main__":
    demo = CustomDemo()
    demo.run()
```

## 演示检查清单

### 单机演示检查项

- [ ] 调度中心成功启动
- [ ] 节点成功注册
- [ ] 任务成功提交
- [ ] 任务成功执行
- [ ] 结果正确返回
- [ ] 资源正确清理

### Web界面演示检查项

- [ ] 界面正常加载
- [ ] 用户注册功能正常
- [ ] 用户登录功能正常
- [ ] 任务提交功能正常
- [ ] 任务监控功能正常
- [ ] 节点管理功能正常

### 局域网演示检查项

- [ ] 调度器可被访问
- [ ] 多节点成功连接
- [ ] 任务正确分发
- [ ] 结果正确汇总
- [ ] 网络通信正常

## 故障排除

### 演示无法启动

1. 检查Python版本（需要3.9+）
2. 检查依赖是否安装完整
3. 检查端口是否被占用

### 节点无法连接

1. 检查网络连接
2. 检查防火墙设置
3. 检查调度器URL是否正确

### 任务执行失败

1. 检查代码语法
2. 检查资源限制
3. 检查沙箱配置

---

**最后更新**: 2026-03-28

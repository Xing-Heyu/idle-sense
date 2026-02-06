# 示例任务集合

这个目录包含各种演示任务，用于展示闲置计算加速器的能力。

## 可用示例

### 1. 简单计算 (`simple_calculation.py`)
- 斐波那契数列计算
- π值计算
- 矩阵乘法
- 质数查找

### 2. 数据处理 (`data_processing.py`)
- 销售数据分析
- 文本统计分析
- 数据聚合和报告生成

### 3. 数学计算 (`math_computation.py`)
- 蒙特卡洛方法计算π
- 数值积分
- 线性代数运算
- 微分方程求解

### 4. 模拟 (`simulation.py`)
- 物理模拟（抛体运动）
- 经济模拟（投资复利）
- 细胞自动机（生命游戏）

### 5. 性能基准测试 (`benchmark.py`)
- CPU浮点性能
- 内存访问性能
- 矩阵运算性能
- 整数运算性能

**修改后（清晰指导）：**
```markdown
### 作为任务提交到调度中心

1. **首先创建一个提交脚本** `submit_fibonacci.py`:
```python
# submit_fibonacci.py
import requests

# 要提交的代码
task_code = """
def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)

result = fib(30)
print(f"斐波那契数列第30项: {result}")
__result__ = result
"""

# 提交到调度中心
response = requests.post(
    "http://localhost:8000/submit",
    json={"code": task_code}
)

print(f"任务ID: {response.json()['task_id']}")  2.  运行提交脚本:   bash 复制   下载    # 确保调度中心已启动
python scheduler/simple_server.py

# 运行提交脚本
python submit_fibonacci.py  3.  查看结果:   bash 复制   下载    curl http://localhost:8000/status/任务ID

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
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
不会就看这个：

作为任务提交到调度中心 python 复制   下载    # 在Python代码中导入示例
from examples import simple_calculation

# 获取任务代码
code = """
# 斐波那契数列计算
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

result = fibonacci(30)
print(f"斐波那契数列第30项: {result}")
__result__ = result
"""

# 通过调度中心提交
import requests
requests.post("http://localhost:8000/submit", json={"code": code})  通过网页界面提交 1.  打开网页界面:  http://localhost:8501   2.  选择"提交任务"标签页  3.  从示例中选择或自定义代码  4.  点击提交按钮   任务特点 计算密集型 •  大量数学运算  •  迭代计算  •  矩阵操作   内存密集型 •  大数据集处理  •  矩阵运算  •  缓存敏感操作   适合分布式计算 •  可并行化任务  •  独立计算单元  •  结果可合并   创建自定义示例 参考现有示例创建新任务： python 复制   下载    # my_example.py
def my_task():
    # 你的计算逻辑
    result = complex_computation()
    return result

if __name__ == "__main__":
    # 直接测试
    print(my_task())  性能提示 1.  选择合适的任务大小： ◦  测试环境：小规模任务  ◦  生产环境：适当规模任务    2.  监控资源使用： ◦  关注内存使用  ◦  控制计算时间  ◦  避免系统过载    3.  结果验证： ◦  验证计算结果  ◦  比较不同实现  ◦  性能分析     text 复制   下载    
## 📁 最终 `examples/` 目录结构  examples/
├── init.py # 包初始化
├── simple_calculation.py # 简单计算示例
├── data_processing.py # 数据处理示例
├── math_computation.py # 数学计算示例
├── simulation.py # 模拟示例
├── benchmark.py # 性能基准测试
└── README.md # 使用说明 text 复制   下载    
## 🎯 示例任务特点

1. **多样性**：覆盖计算、数据处理、模拟、基准测试
2. **实用性**：真实世界的计算任务
3. **可调性**：参数可调整以适应不同硬件
4. **教育性**：包含详细注释和解释
5. **可验证**：提供预期结果和验证方法

## 🚀 使用方法

```bash
# 直接运行演示
python examples/simple_calculation.py

# 导入使用
from examples import benchmark
results = benchmark.benchmark_suite()

# 作为任务代码提交
with open('examples/simple_calculation.py', 'r') as f:
    task_code = f.read()
# 提交到调度中心  示例任务脚本已创建完成！ 现在有了丰富的演示材料，可以展示系统的各种能力。

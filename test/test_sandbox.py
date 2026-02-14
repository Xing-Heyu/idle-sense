"""
test_sandbox.py
测试安全沙箱功能
"""

import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sandbox import CodeSandbox


def test_safe_code():
    """测试安全代码"""
    print("=" * 60)
    print("测试安全代码")
    print("=" * 60)
    
    sandbox = CodeSandbox()
    
    # 测试1: 基本数学计算
    safe_code_1 = """
import math
import random

# 安全计算示例
result = 0
for i in range(1000):
    result += math.sqrt(i) * random.random()

print(f"安全计算完成，结果: {result:.4f}")
"""
    
    print("\n测试1: 基本数学计算")
    result = sandbox.execute_safe(safe_code_1, timeout=10)
    print(f"成功: {result['success']}")
    print(f"输出: {result['output']}")
    print(f"执行时间: {result['execution_time']}秒")
    
    # 测试2: 数据处理
    safe_code_2 = """
import statistics
import json

# 数据处理示例
data = [i * 1.5 for i in range(100)]
stats = {
    'mean': statistics.mean(data),
    'stdev': statistics.stdev(data),
    'min': min(data),
    'max': max(data)
}

print("数据处理完成:")
for key, value in stats.items():
    print(f"{key}: {value:.2f}")
"""
    
    print("\n测试2: 数据处理")
    result = sandbox.execute_safe(safe_code_2, timeout=10)
    print(f"成功: {result['success']}")
    print(f"输出: {result['output']}")
    print(f"执行时间: {result['execution_time']}秒")


def test_dangerous_code():
    """测试危险代码"""
    print("\n" + "=" * 60)
    print("测试危险代码")
    print("=" * 60)
    
    sandbox = CodeSandbox()
    
    # 测试1: 危险系统调用
    dangerous_code_1 = """
import os
os.system('rm -rf /')  # 危险操作
print("这行代码不应该执行")
"""
    
    print("\n测试1: 危险系统调用")
    result = sandbox.execute_safe(dangerous_code_1, timeout=5)
    print(f"成功: {result['success']}")
    print(f"错误: {result.get('error', '无错误')}")
    
    # 测试2: 禁止的模块导入
    dangerous_code_2 = """
import subprocess
subprocess.call(['ls', '-la'])  # 危险操作
print("这行代码不应该执行")
"""
    
    print("\n测试2: 禁止的模块导入")
    safety_check = sandbox.check_code_safety(dangerous_code_2)
    print(f"安全检查: {safety_check['safe']}")
    print(f"错误信息: {safety_check.get('error', '无错误')}")
    
    # 测试3: 危险的内置函数
    dangerous_code_3 = """
result = eval('__import__(\"os\").system(\"dir\")')  # 危险操作
print(f"结果: {result}")
"""
    
    print("\n测试3: 危险的内置函数")
    safety_check = sandbox.check_code_safety(dangerous_code_3)
    print(f"安全检查: {safety_check['safe']}")
    print(f"错误信息: {safety_check.get('error', '无错误')}")


def test_performance():
    """测试性能"""
    print("\n" + "=" * 60)
    print("测试性能")
    print("=" * 60)
    
    sandbox = CodeSandbox()
    
    # 性能测试代码
    perf_code = """
import time

# 模拟计算密集型任务
start = time.time()

# 计算斐波那契数列
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

result = fibonacci(25)
end = time.time()

print(f"斐波那契数列第25项: {result}")
print(f"计算耗时: {end - start:.3f}秒")
"""
    
    print("\n性能测试: 计算密集型任务")
    result = sandbox.execute_safe(perf_code, timeout=30)
    print(f"成功: {result['success']}")
    print(f"输出: {result['output']}")
    print(f"执行时间: {result['execution_time']}秒")


def test_system_integration():
    """测试系统集成"""
    print("\n" + "=" * 60)
    print("测试系统集成")
    print("=" * 60)
    
    # 测试调度器集成
    try:
        import requests
        
        # 测试安全代码提交
        safe_test_code = """
import math
print(f"圆周率: {math.pi}")
print("安全代码测试通过")
"""
        
        print("测试调度器API集成")
        response = requests.post(
            "http://localhost:8000/submit",
            json={
                "code": safe_test_code,
                "timeout": 30,
                "resources": {"cpu": 1.0, "memory": 512}
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ 安全代码提交成功")
            result = response.json()
            print(f"任务ID: {result.get('task_id')}")
            print(f"安全检查: {result.get('safety_check', 'N/A')}")
        else:
            print(f"❌ 提交失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            
    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        print("提示: 请确保调度器正在运行 (python scheduler/simple_server.py)")


if __name__ == "__main__":
    print("闲置计算加速器 - 安全沙箱测试")
    print("=" * 60)
    
    # 运行测试
    test_safe_code()
    test_dangerous_code()
    test_performance()
    test_system_integration()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

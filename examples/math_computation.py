"""
examples/math_computation.py
数学计算示例 - 展示科学计算能力
"""

def monte_carlo_pi(samples=1000000):
    """蒙特卡洛方法计算π"""
    import random
    import math
    import time
    
    print("蒙特卡洛方法计算π")
    print(f"样本数: {samples:,}")
    
    start_time = time.time()
    
    inside_circle = 0
    for _ in range(samples):
        x = random.random()
        y = random.random()
        
        if x*x + y*y <= 1.0:
            inside_circle += 1
    
    pi_estimate = 4.0 * inside_circle / samples
    error = abs(pi_estimate - math.pi)
    
    elapsed = time.time() - start_time
    
    print(f"π的估计值: {pi_estimate:.10f}")
    print(f"真实π值: {math.pi:.10f}")
    print(f"误差: {error:.10f}")
    print(f"计算时间: {elapsed:.3f}秒")
    print(f"速度: {samples/elapsed:,.0f} 样本/秒")
    
    return pi_estimate

def numerical_integration():
    """数值积分"""
    import math
    
    print("\n" + "-" * 60)
    print("数值积分演示")
    print("-" * 60)
    
    # 积分 ∫₀¹ sin(x²) dx
    def f(x):
        return math.sin(x * x)
    
    # 使用梯形法则
    n = 100000
    a, b = 0, 1
    h = (b - a) / n
    
    integral = 0.5 * (f(a) + f(b))
    for i in range(1, n):
        integral += f(a + i * h)
    
    integral *= h
    
    # 精确值（通过更精确的方法）
    exact_value = 0.3102683017233811
    
    print(f"函数: f(x) = sin(x²)")
    print(f"区间: [{a}, {b}]")
    print(f"分割数: {n:,}")
    print(f"数值积分结果: {integral:.10f}")
    print(f"精确值: {exact_value:.10f}")
    print(f"误差: {abs(integral - exact_value):.10f}")
    
    return integral

def linear_algebra_operations():
    """线性代数运算"""
    import time
    import random
    
    print("\n" + "-" * 60)
    print("线性代数运算演示")
    print("-" * 60)
    
    # 创建矩阵
    size = 200
    print(f"创建 {size}×{size} 矩阵...")
    
    # 随机矩阵
    A = [[random.random() for _ in range(size)] for _ in range(size)]
    B = [[random.random() for _ in range(size)] for _ in range(size)]
    
    # 矩阵加法
    print("执行矩阵加法...")
    start = time.time()
    C = [[A[i][j] + B[i][j] for j in range(size)] for i in range(size)]
    add_time = time.time() - start
    
    # 矩阵乘法
    print("执行矩阵乘法...")
    start = time.time()
    D = [[0 for _ in range(size)] for _ in range(size)]
    for i in range(size):
        for j in range(size):
            for k in range(size):
                D[i][j] += A[i][k] * B[k][j]
    mul_time = time.time() - start
    
    print(f"\n性能结果:")
    print(f"矩阵加法: {add_time:.3f}秒")
    print(f"矩阵乘法: {mul_time:.3f}秒")
    print(f"乘法/加法时间比: {mul_time/add_time:.1f}x")
    
    # 验证结果（检查第一个元素）
    sum_check = sum(C[0])
    mul_check = sum(D[0])
    
    return {
        'matrix_size': size,
        'addition_time': add_time,
        'multiplication_time': mul_time,
        'sum_first_row': sum_check,
        'mul_first_row': mul_check
    }

def solve_differential_equation():
    """求解微分方程"""
    print("\n" + "-" * 60)
    print("微分方程求解演示")
    print("-" * 60)
    
    # 简单微分方程: dy/dx = -y, y(0) = 1
    # 解析解: y = exp(-x)
    
    def euler_method(f, y0, x0, x_end, steps=1000):
        """欧拉方法"""
        h = (x_end - x0) / steps
        x = x0
        y = y0
        result = [(x, y)]
        
        for _ in range(steps):
            y = y + h * f(x, y)
            x = x + h
            result.append((x, y))
        
        return result
    
    # 定义微分方程
    def dy_dx(x, y):
        return -y
    
    # 求解
    solution = euler_method(dy_dx, y0=1.0, x0=0.0, x_end=5.0, steps=1000)
    
    # 获取最终值
    x_final, y_final = solution[-1]
    exact_final = math.exp(-x_final)
    error = abs(y_final - exact_final)
    
    print(f"微分方程: dy/dx = -y, y(0) = 1")
    print(f"数值解 (x={x_final:.2f}): y = {y_final:.6f}")
    print(f"精确解 (x={x_final:.2f}): y = {exact_final:.6f}")
    print(f"误差: {error:.6f}")
    print(f"相对误差: {error/exact_final*100:.2f}%")
    
    return {
        'equation': 'dy/dx = -y',
        'initial_condition': 'y(0) = 1',
        'numerical_solution': y_final,
        'exact_solution': exact_final,
        'error': error
    }

def run_math_computation_demo():
    """运行数学计算演示"""
    print("=" * 60)
    print("数学计算演示")
    print("=" * 60)
    
    results = {}
    
    results['monte_carlo_pi'] = monte_carlo_pi(500000)
    results['integration'] = numerical_integration()
    results['linear_algebra'] = linear_algebra_operations()
    results['differential_eq'] = solve_differential_equation()
    
    print("\n" + "=" * 60)
    print("数学计算演示完成!")
    print("=" * 60)
    
    return results

if __name__ == "__main__":
    import math
    run_math_computation_demo()

"""
examples/simple_calculation.py
简单计算示例 - 展示基本功能
"""

def calculate_fibonacci(n=30):
    """计算斐波那契数列"""
    def fib(x):
        if x <= 1:
            return x
        return fib(x-1) + fib(x-2)
    
    result = fib(n)
    print(f"斐波那契数列第 {n} 项: {result}")
    return result

def calculate_pi_series(iterations=1000000):
    """通过级数计算π"""
    pi = 0
    for i in range(iterations):
        pi += ((-1) ** i) / (2 * i + 1)
    pi *= 4
    
    print(f"通过 {iterations} 次迭代计算的π: {pi}")
    print(f"与math.pi的误差: {abs(pi - 3.141592653589793)}")
    return pi

def matrix_multiplication(size=100):
    """矩阵乘法（性能测试）"""
    import random
    import time
    
    # 创建随机矩阵
    A = [[random.random() for _ in range(size)] for _ in range(size)]
    B = [[random.random() for _ in range(size)] for _ in range(size)]
    C = [[0 for _ in range(size)] for _ in range(size)]
    
    # 矩阵乘法
    start_time = time.time()
    
    for i in range(size):
        for j in range(size):
            for k in range(size):
                C[i][j] += A[i][k] * B[k][j]
    
    elapsed = time.time() - start_time
    
    print(f"{size}×{size} 矩阵乘法完成")
    print(f"计算时间: {elapsed:.3f} 秒")
    print(f"性能: {(size**3) / elapsed / 1e6:.2f} MFLOPS")
    
    return C[0][0]  # 返回一个标量用于验证

def prime_numbers(limit=100000):
    """查找质数（计算密集型）"""
    import time
    
    start_time = time.time()
    
    primes = []
    is_prime = [True] * (limit + 1)
    is_prime[0:2] = [False, False]
    
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            for j in range(i*i, limit+1, i):
                is_prime[j] = False
    
    primes = [i for i, prime in enumerate(is_prime) if prime]
    
    elapsed = time.time() - start_time
    
    print(f"找到 {len(primes)} 个质数（1-{limit}）")
    print(f"最大质数: {primes[-1] if primes else '无'}")
    print(f"计算时间: {elapsed:.3f} 秒")
    print(f"速度: {len(primes)/elapsed:.0f} 质数/秒")
    
    return primes[:10]  # 返回前10个质数

def run_simple_demo():
    """运行简单计算演示"""
    print("=" * 60)
    print("简单计算演示")
    print("=" * 60)
    
    results = {}
    
    # 1. 斐波那契数列
    print("\n1. 计算斐波那契数列...")
    results['fibonacci'] = calculate_fibonacci(30)
    
    # 2. 计算π
    print("\n2. 通过级数计算π...")
    results['pi'] = calculate_pi_series(100000)
    
    # 3. 矩阵乘法
    print("\n3. 矩阵乘法性能测试...")
    results['matrix'] = matrix_multiplication(50)  # 50x50矩阵
    
    # 4. 查找质数
    print("\n4. 查找质数...")
    results['primes'] = prime_numbers(50000)
    
    print("\n" + "=" * 60)
    print("演示完成!")
    print(f"计算结果: {list(results.keys())}")
    
    return results

if __name__ == "__main__":
    # 当直接运行时，执行演示
    run_simple_demo()

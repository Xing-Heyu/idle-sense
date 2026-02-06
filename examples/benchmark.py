"""
examples/benchmark.py
性能基准测试 - 测试系统计算能力
"""

def benchmark_suite():
    """综合性能基准测试"""
    import time
    import math
    import random
    
    print("=" * 60)
    print("性能基准测试套件")
    print("=" * 60)
    
    results = {}
    
    # 1. CPU浮点性能测试
    print("\n1. CPU浮点性能 (Mandelbrot集)...")
    start = time.time()
    
    def mandelbrot(c, max_iter=100):
        z = 0
        for i in range(max_iter):
            if abs(z) > 2:
                return i
            z = z*z + c
        return max_iter
    
    # 计算小区域
    width, height = 200, 200
    x_min, x_max = -2.0, 1.0
    y_min, y_max = -1.5, 1.5
    
    iterations = 0
    for y in range(height):
        for x in range(width):
            real = x_min + (x / width) * (x_max - x_min)
            imag = y_min + (y / height) * (y_max - y_min)
            c = complex(real, imag)
            iterations += mandelbrot(c, 50)
    
    cpu_time = time.time() - start
    cpu_score = iterations / cpu_time
    
    print(f"  计算 {width*height:,} 个点")
    print(f"  总迭代数: {iterations:,}")
    print(f"  计算时间: {cpu_time:.3f} 秒")
    print(f"  CPU分数: {cpu_score:,.0f} 迭代/秒")
    
    results['cpu_float'] = {
        'time': cpu_time,
        'iterations': iterations,
        'score': cpu_score
    }
    
    # 2. 内存访问性能
    print("\n2. 内存访问性能...")
    size = 1000000  # 100万个元素
    data = [random.random() for _ in range(size)]
    
    start = time.time()
    
    # 顺序访问
    sum1 = 0.0
    for i in range(size):
        sum1 += data[i]
    
    # 随机访问
    sum2 = 0.0
    indices = list(range(size))
    random.shuffle(indices)
    for i in indices:
        sum2 += data[i]
    
    mem_time = time.time() - start
    mem_score = 2 * size / mem_time  # 两次访问
    
    print(f"  数据大小: {size:,} 个浮点数")
    print(f"  顺序+随机访问时间: {mem_time:.3f} 秒")
    print(f"  内存分数: {mem_score:,.0f} 访问/秒")
    
    results['memory_access'] = {
        'time': mem_time,
        'size': size,
        'score': mem_score,
        'checksum': sum1 + sum2
    }
    
    # 3. 矩阵运算性能
    print("\n3. 矩阵运算性能...")
    n = 200
    A = [[random.random() for _ in range(n)] for _ in range(n)]
    B = [[random.random() for _ in range(n)] for _ in range(n)]
    
    start = time.time()
    
    # 矩阵乘法
    C = [[0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            for k in range(n):
                C[i][j] += A[i][k] * B[k][j]
    
    matrix_time = time.time() - start
    flops = 2 * n**3 / matrix_time  # 浮点运算次数/秒
    
    print(f"  矩阵大小: {n}×{n}")
    print(f"  浮点运算数: {2*n**3:,}")
    print(f"  计算时间: {matrix_time:.3f} 秒")
    print(f"  性能: {flops/1e6:.2f} MFLOPS")
    
    results['matrix_multiply'] = {
        'size': n,
        'time': matrix_time,
        'flops': flops,
        'mflops': flops/1e6
    }
    
    # 4. 整数运算性能
    print("\n4. 整数运算性能...")
    start = time.time()
    
    # 计算质数
    limit = 100000
    is_prime = [True] * (limit + 1)
    is_prime[0:2] = [False, False]
    
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            for j in range(i*i, limit+1, i):
                is_prime[j] = False
    
    primes = [i for i, prime in enumerate(is_prime) if prime]
    
    int_time = time.time() - start
    int_score = len(primes) / int_time
    
    print(f"  范围: 1-{limit}")
    print(f"  找到质数: {len(primes)}")
    print(f"  计算时间: {int_time:.3f} 秒")
    print(f"  整数分数: {int_score:,.0f} 质数/秒")
    
    results['integer_ops'] = {
        'limit': limit,
        'primes_found': len(primes),
        'time': int_time,
        'score': int_score
    }
    
    # 综合评分
    print("\n" + "=" * 60)
    print("综合性能评分")
    print("=" * 60)
    
    # 归一化分数 (越高越好)
    normalized_scores = {
        'CPU浮点': cpu_score / 1000,
        '内存访问': mem_score / 10000,
        '矩阵运算': flops / 1e6,
        '整数运算': int_score / 100
    }
    
    total_score = sum(normalized_scores.values())
    avg_score = total_score / len(normalized_scores)
    
    print(f"\n各项得分:")
    for name, score in normalized_scores.items():
        stars = '★' * min(int(score), 5)
        print(f"  {name:10} {score:6.1f} {stars}")
    
    print(f"\n平均得分: {avg_score:.1f}")
    print(f"综合评级: ", end="")
    
    if avg_score >= 4.0:
        print("★★★★★ 优秀")
    elif avg_score >= 3.0:
        print("★★★★☆ 良好")
    elif avg_score >= 2.0:
        print("★★★☆☆ 一般")
    elif avg_score >= 1.0:
        print("★★☆☆☆ 及格")
    else:
        print("★☆☆☆☆ 较差")
    
    print(f"\n基准测试完成!")
    
    results['summary'] = {
        'normalized_scores': normalized_scores,
        'total_score': total_score,
        'average_score': avg_score
    }
    
    return results

def compare_with_reference():
    """与参考性能比较"""
    print("\n" + "=" * 60)
    print("性能比较 (参考值)")
    print("=" * 60)
    
    # 参考性能 (基于现代CPU)
    reference = {
        'CPU浮点': 500.0,  # 千迭代/秒
        '内存访问': 80.0,   # 万访问/秒
        '矩阵运算': 100.0,  # MFLOPS
        '整数运算': 300.0   # 质数/秒
    }
    
    # 获取当前性能
    current = benchmark_suite()
    
    if 'summary' in current:
        current_scores = current['summary']['normalized_scores']
        
        print(f"\n性能对比:")
        print(f"{'测试项目':10} {'当前':>8} {'参考':>8} {'比例':>8}")
        print("-" * 40)
        
        for test in reference:
            cur = current_scores.get(test, 0)
            ref = reference[test]
            ratio = cur / ref * 100
            
            print(f"{test:10} {cur:8.1f} {ref:8.1f} {ratio:7.1f}%")
        
       # 总体比例
        avg_ratio = sum(current_scores.get(k, 0)/v for k, v in reference.items()) / len(reference) * 100
        print(f"\n总体性能: {avg_ratio:.1f}% 参考值")
    
    return current

if __name__ == "__main__":
    print("闲置计算节点性能基准测试")
    print("=" * 60)
    
    choice = input("运行哪种测试?\n1. 完整基准测试\n2. 与参考值比较\n选择 [1]: ").strip()
    
    if choice == "2":
        compare_with_reference()
    else:
        benchmark_suite()

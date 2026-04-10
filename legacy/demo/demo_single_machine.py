"""
demo/demo_single_machine.py
单机演示脚本 - 在一台电脑上展示完整流程
"""

import subprocess
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_header(title):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_step(step, description):
    """打印步骤"""
    print(f"\n[{step}] {description}")
    print("-" * 40)


def start_scheduler():
    """启动调度中心"""
    print_step("1", "启动调度中心...")

    # 检查调度中心是否已在运行
    try:
        import requests

        response = requests.get("http://localhost:8000/", timeout=2)
        if response.status_code == 200:
            print("  调度中心已在运行")
            return None
    except requests.RequestException:
        pass

    # 启动调度中心子进程
    scheduler_proc = subprocess.Popen(
        [sys.executable, "scheduler/simple_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    print(f"  调度中心已启动 (PID: {scheduler_proc.pid})")

    # 等待调度中心就绪
    print("  等待调度中心就绪...", end="", flush=True)
    for _ in range(30):  # 最多等待30秒
        try:
            import requests

            response = requests.get("http://localhost:8000/", timeout=1)
            if response.status_code == 200:
                print(" ✓")
                print("  地址: http://localhost:8000")
                return scheduler_proc
        except requests.RequestException:
            print(".", end="", flush=True)
            time.sleep(1)

    print("\n  ✗ 调度中心启动超时")
    return None


def start_node():
    """启动计算节点"""
    print_step("2", "启动计算节点...")

    node_proc = subprocess.Popen(
        [sys.executable, "node/simple_client.py", "--scheduler", "http://localhost:8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    print(f"  计算节点已启动 (PID: {node_proc.pid})")
    print("  等待节点注册...", end="", flush=True)

    # 等待节点注册
    for _ in range(15):
        try:
            import requests

            response = requests.get("http://localhost:8000/nodes", timeout=1)
            if response.status_code == 200:
                data = response.json()
                if data.get("total_nodes", 0) > 0:
                    print(" ✓")
                    print(f"  节点数: {data.get('total_nodes')}")
                    print(f"  闲置节点: {data.get('total_idle', 0)}")
                    return node_proc
        except requests.RequestException:
            pass
        print(".", end="", flush=True)
        time.sleep(1)

    print("\n  ⚠ 节点注册较慢，继续演示...")
    return node_proc


def submit_demo_task():
    """提交演示任务"""
    print_step("3", "提交演示任务...")

    # 演示任务代码
    demo_code = """
# 演示任务: 计算斐波那契数列和π
import time
import math

print("🎯 演示任务开始执行")
print("=" * 40)

# 1. 计算斐波那契数列
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

start = time.time()
fib_result = fibonacci(30)
fib_time = time.time() - start
print(f"1. 斐波那契数列第30项: {fib_result}")
print(f"   计算时间: {fib_time:.3f}秒")

# 2. 计算π（蒙特卡洛方法）
print()
print("2. 使用蒙特卡洛方法计算π")
samples = 1000000
inside = 0

for i in range(samples):
    x = (i * 1.2345) % 1.0  # 伪随机
    y = (i * 2.3456) % 1.0
    if x*x + y*y <= 1.0:
        inside += 1

    # 显示进度
    if (i + 1) % 100000 == 0:
        progress = (i + 1) / samples * 100
        pi_estimate = 4.0 * inside / (i + 1)
        print(f"   进度: {progress:.0f}% | π ≈ {pi_estimate:.6f}")

pi_estimate = 4.0 * inside / samples
pi_error = abs(pi_estimate - math.pi)

print(f"   π的估计值: {pi_estimate:.10f}")
print(f"   真实π值: {math.pi:.10f}")
print(f"   误差: {pi_error:.10f}")

# 3. 矩阵运算（小型）
print()
print("3. 矩阵乘法演示")
size = 50
matrix_a = [[(i + j) % 100 / 100 for j in range(size)] for i in range(size)]
matrix_b = [[(i - j) % 100 / 100 for j in range(size)] for i in range(size)]
matrix_c = [[0 for _ in range(size)] for _ in range(size)]

for i in range(size):
    for j in range(size):
        for k in range(size):
            matrix_c[i][j] += matrix_a[i][k] * matrix_b[k][j]

print(f"   {size}×{size} 矩阵乘法完成")
print(f"   结果矩阵第一个元素: {matrix_c[0][0]:.6f}")

print()
print("=" * 40)
print("✅ 演示任务完成!")
__result__ = {
    "fibonacci_30": fib_result,
    "pi_estimate": pi_estimate,
    "pi_error": pi_error,
    "matrix_size": size,
    "execution_time": time.time() - start
}
"""

    try:
        import requests

        payload = {"code": demo_code, "timeout": 60, "resources": {"cpu": 1.0, "memory": 512}}

        response = requests.post("http://localhost:8000/submit", json=payload, timeout=10)

        if response.status_code == 200:
            data = response.json()
            task_id = data.get("task_id")
            print("  ✅ 任务提交成功!")
            print(f"     任务ID: {task_id}")
            print(f"     状态: {data.get('status', 'N/A')}")
            return task_id
        else:
            print(f"  ✗ 任务提交失败: HTTP {response.status_code}")
            return None

    except Exception as e:
        print(f"  ✗ 提交任务时出错: {e}")
        return None


def monitor_task(task_id):
    """监控任务进度"""
    print_step("4", "监控任务执行...")

    try:
        import requests

        print(f"  任务ID: {task_id}")
        print("  等待任务完成...")

        for attempt in range(60):  # 最多等待60秒
            response = requests.get(f"http://localhost:8000/status/{task_id}", timeout=5)

            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")

                # 显示进度
                if attempt % 5 == 0:  # 每5秒显示一次状态
                    print(f"    状态: {status}", end="")
                    if status == "running":
                        print(" 🔄", end="")
                    elif status == "completed":
                        print(" ✅", end="")
                    elif status == "failed":
                        print(" ❌", end="")
                    print()

                if status == "completed":
                    print("\n  ✅ 任务完成!")

                    # 显示结果
                    result = data.get("result", "")
                    print(f"  执行节点: {data.get('executed_on', '未知')}")

                    # 解析并显示重要结果
                    if result:
                        lines = result.split("\n")
                        print("  重要输出:")
                        for line in lines[:10]:  # 显示前10行
                            if line.strip() and not line.startswith("  "):
                                print(f"    {line}")

                    return True
                elif status == "failed":
                    print("\n  ❌ 任务失败")
                    return False
                elif status == "pending":
                    pass  # 继续等待

            time.sleep(1)

        print("\n  ⚠ 任务监控超时")
        return False

    except Exception as e:
        print(f"  ✗ 监控任务时出错: {e}")
        return False


def check_system_status():
    """检查系统状态"""
    print_step("5", "检查系统状态...")

    try:
        import requests

        # 调度中心状态
        response = requests.get("http://localhost:8000/", timeout=3)
        if response.status_code == 200:
            data = response.json()
            print(f"  调度中心: ✅ {data.get('service', 'N/A')}")
            print(f"    状态: {data.get('status', 'N/A')}")
            print(f"    队列任务: {data.get('queue_size', 0)}")

        # 节点状态
        response = requests.get("http://localhost:8000/nodes", timeout=3)
        if response.status_code == 200:
            data = response.json()
            print(f"  计算节点: {data.get('total_nodes', 0)} 个")
            print(f"    闲置节点: {data.get('total_idle', 0)}")
            print(f"    忙碌节点: {data.get('total_nodes', 0) - data.get('total_idle', 0)}")

        # 任务统计
        response = requests.get("http://localhost:8000/stats", timeout=3)
        if response.status_code == 200:
            data = response.json()
            tasks = data.get("tasks", {})
            print("  任务统计:")
            print(f"    总任务: {tasks.get('total', 0)}")
            print(f"    已完成: {tasks.get('completed', 0)}")
            print(f"    平均用时: {tasks.get('avg_time', 0):.1f}秒")

        return True

    except Exception as e:
        print(f"  ⚠ 获取系统状态时出错: {e}")
        return False


def cleanup(processes):
    """清理进程"""
    print_step("6", "清理演示环境...")

    for name, proc in processes.items():
        if proc and proc.poll() is None:  # 进程还在运行
            print(f"  停止 {name}...", end="", flush=True)
            proc.terminate()
            try:
                proc.wait(timeout=5)
                print(" ✓")
            except subprocess.TimeoutExpired:
                print(" ⚠ (强制终止)")
                proc.kill()

    print("  演示环境清理完成")


def run_single_machine_demo():
    """运行单机演示"""
    print_header("闲置计算加速器 - 单机演示")
    print("在一台电脑上展示完整的调度、执行、监控流程")
    print()

    processes = {}

    try:
        # 1. 启动调度中心
        scheduler_proc = start_scheduler()
        if scheduler_proc is None and not check_scheduler_exists():
            print("  ✗ 无法启动或连接到调度中心，演示中止")
            return False

        processes["scheduler"] = scheduler_proc

        # 2. 启动计算节点
        node_proc = start_node()
        processes["node"] = node_proc

        # 3. 提交演示任务
        task_id = submit_demo_task()
        if not task_id:
            print("  ✗ 无法提交任务，演示中止")
            return False

        # 4. 监控任务执行
        task_success = monitor_task(task_id)

        # 5. 检查系统状态
        check_system_status()

        print_header("演示完成")
        if task_success:
            print("✅ 单机演示成功完成!")
            print()
            print("演示内容:")
            print("  • 调度中心启动和运行")
            print("  • 计算节点注册和闲置检测")
            print("  • 任务提交和队列管理")
            print("  • 任务执行和结果返回")
            print("  • 系统状态监控")
            print()
            print("🎉 闲置计算加速器基本功能验证通过!")
            return True
        else:
            print("⚠ 演示部分完成，但任务执行可能有问题")
            return False

    except KeyboardInterrupt:
        print("\n\n演示被用户中断")
        return False
    except Exception as e:
        print(f"\n演示出错: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # 清理
        cleanup(processes)


def check_scheduler_exists():
    """检查调度中心是否已存在"""
    try:
        import requests

        response = requests.get("http://localhost:8000/", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


if __name__ == "__main__":
    # 运行单机演示
    success = run_single_machine_demo()

    print("\n" + "=" * 60)
    if success:
        print("✅ 演示成功!")
        print("\n下一步:")
        print("  1. 尝试多机演示: python demo/demo_local_network.py")
        print("  2. 使用网页界面: streamlit run web_interface.py")
        print("  3. 查看示例任务: python examples/simple_calculation.py")
    else:
        print("❌ 演示失败")
        print("\n故障排除:")
        print("  1. 检查Python依赖: pip install -r requirements.txt")
        print("  2. 手动启动调度中心: python scheduler/simple_server.py")
        print("  3. 检查端口占用: netstat -an | grep 8000")

    sys.exit(0 if success else 1)

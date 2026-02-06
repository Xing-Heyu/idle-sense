"""
demo/demo_web_interface.py
网页界面演示脚本 - 展示网页控制台功能
"""

import os
import sys
import time
import webbrowser
import threading
import subprocess
from pathlib import Path

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

def check_prerequisites():
    """检查前置条件"""
    print_step("1", "检查前置条件")
    
    requirements = [
        ("Python 3.8+", sys.version_info >= (3, 8)),
        ("requests 库", True),  # 稍后检查
        ("streamlit 库", True),
    ]
    
    all_ok = True
    
    for req, ok in requirements:
        if req == "requests 库":
            try:
                import requests
                ok = True
                version = requests.__version__
            except ImportError:
                ok = False
                version = "未安装"
        
        elif req == "streamlit 库":
            try:
                import streamlit
                ok = True
                version = streamlit.__version__
            except ImportError:
                ok = False
                version = "未安装"
        
        else:
            version = ""
        
        status = "✅" if ok else "❌"
        print(f"  {status} {req:15} {version}")
        
        if not ok:
            all_ok = False
    
    if not all_ok:
        print("\n  ⚠ 缺少必要组件，请运行:")
        print("     pip install -r requirements.txt")
        return False
    
    return True

def start_services():
    """启动所需服务"""
    print_step("2", "启动服务")
    
    processes = {}
    
    # 1. 启动调度中心
    print("  启动调度中心...")
    scheduler_proc = subprocess.Popen(
        [sys.executable, "scheduler/simple_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    processes['scheduler'] = scheduler_proc
    print(f"    PID: {scheduler_proc.pid}")
    
    # 等待调度中心启动
    print("  等待调度中心就绪...", end="", flush=True)
    for _ in range(30):
        try:
            import requests
            response = requests.get("http://localhost:8000/", timeout=1)
            if response.status_code == 200:
                print(" ✓")
                break
        except:
            print(".", end="", flush=True)
            time.sleep(1)
    else:
        print("\n  ⚠ 调度中心启动较慢")
    
    # 2. 启动计算节点
    print("\n  启动计算节点...")
    node_proc = subprocess.Popen(
        [sys.executable, "node/simple_client.py", "--scheduler", "http://localhost:8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    processes['node'] = node_proc
    print(f"    PID: {node_proc.pid}")
    
    # 3. 启动网页界面
    print("\n  启动网页界面...")
    web_proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "web_interface.py", "--server.port", "8501"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    processes['web'] = web_proc
    print(f"    PID: {web_proc.pid}")
    
    # 等待网页界面启动
    print("  等待网页界面就绪...", end="", flush=True)
    for _ in range(30):
        try:
            import requests
            response = requests.get("http://localhost:8501", timeout=1)
            if response.status_code == 200:
                print(" ✓")
                break
        except:
            print(".", end="", flush=True)
            time.sleep(1)
    else:
        print("\n  ⚠ 网页界面启动较慢")
    
    return processes

def open_browser():
    """打开浏览器"""
    print_step("3", "打开网页界面")
    
    urls = [
        ("调度中心API", "http://localhost:8000"),
        ("网页控制台", "http://localhost:8501"),
    ]
    
    print("  可用界面:")
    for name, url in urls:
        print(f"    • {name}: {url}")
    
    # 询问打开哪个
    print("\n  要打开浏览器吗？")
    choice = input("  打开网页控制台？(y/n) [y]: ").strip().lower()
    
    if choice in ['y', 'yes', '']:
        print("  正在打开浏览器...")
        webbrowser.open("http://localhost:8501")
        print("  ✅ 浏览器已打开")
    
    return True

def run_demo_tasks():
    """运行演示任务"""
    print_step("4", "运行演示任务")
    
    print("  将自动提交一些演示任务...")
    
    # 演示任务列表
    demo_tasks = [
        {
            "name": "快速计算",
            "code": """
# 快速计算演示
import time

start = time.time()

# 简单计算
result = 0
for i in range(1000000):
    result += i * 0.0001

elapsed = time.time() - start

print("快速计算完成")
print(f"结果: {result:.4f}")
print(f"时间: {elapsed:.3f}秒")

__result__ = f"计算完成: {result:.4f} ({elapsed:.3f}秒)"
""",
            "description": "简单的循环计算，展示基本功能"
        },
        {
            "name": "数据处理",
            "code": """
# 数据处理演示
import random
import statistics

# 生成数据
data = [random.gauss(100, 15) for _ in range(10000)]

# 计算统计
stats = {
    "count": len(data),
    "mean": statistics.mean(data),
    "stdev": statistics.stdev(data),
    "min": min(data),
    "max": max(data),
    "median": statistics.median(data)
}

print("数据处理完成")
for key, value in stats.items():
    print(f"{key}: {value:.2f}")

__result__ = stats
""",
            "description": "数据统计计算，展示分析能力"
        },
        {
            "name": "数学计算",
            "code": """
# 数学计算演示
import math

# 计算一些数学常数和函数
results = {}

# π的相关计算
results["pi"] = math.pi
results["pi_squared"] = math.pi ** 2
results["sqrt_pi"] = math.sqrt(math.pi)

# 三角函数
angle = math.pi / 4  # 45度
results["sin_45"] = math.sin(angle)
results["cos_45"] = math.cos(angle)
results["tan_45"] = math.tan(angle)

# 对数和指数
results["log_10"] = math.log(10)
results["exp_1"] = math.exp(1)
results["e"] = math.e

print("数学计算完成")
for key, value in results.items():
    print(f"{key}: {value:.6f}")

__result__ = results
""",
            "description": "数学函数计算，展示科学计算能力"
        }
    ]
    
    import requests
    
    submitted_tasks = []
    
    for i, task in enumerate(demo_tasks):
        print(f"\n  提交任务 {i+1}: {task['name']}")
        print(f"    描述: {task['description']}")
        
        try:
            payload = {
                "code": task["code"],
                "timeout": 30,
                "resources": {"cpu": 1.0, "memory": 256}
            }
            
            response = requests.post("http://localhost:8000/submit", json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                task_id = data.get("task_id")
                submitted_tasks.append({
                    "id": task_id,
                    "name": task["name"],
                    "status": "submitted"
                })
                print(f"    ✅ 提交成功 (ID: {task_id})")
            else:
                print(f"    ❌ 提交失败: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ 提交错误: {e}")
    
    # 监控任务执行
    if submitted_tasks:
        print(f"\n  监控任务执行...")
        print("  等待5秒让任务开始执行...")
        time.sleep(5)
        
        completed = 0
        for task in submitted_tasks:
            try:
                response = requests.get(f"http://localhost:8000/status/{task['id']}", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unknown")
                    task["status"] = status
                    
                    if status == "completed":
                        completed += 1
                        print(f"    ✅ {task['name']}: 已完成")
                    elif status == "running":
                        print(f"    🔄 {task['name']}: 执行中")
                    elif status == "failed":
                        print(f"    ❌ {task['name']}: 失败")
            except:
                pass
        
        print(f"\n  任务完成: {completed}/{len(submitted_tasks)}")
    
    return submitted_tasks

def show_system_status():
    """显示系统状态"""
    print_step("5", "系统状态检查")
    
    try:
        import requests
        
        print("  检查系统各组件状态...")
        
        # 调度中心状态
        try:
            response = requests.get("http://localhost:8000/", timeout=3)
            if response.status_code == 200:
                data = response.json()
                print(f"    ✅ 调度中心: {data.get('service', 'N/A')}")
                print(f"       状态: {data.get('status', 'N/A')}")
                print(f"       版本: {data.get('version', 'N/A')}")
                print(f"       队列: {data.get('queue_size', 0)} 个任务")
        except:
            print(f"    ❌ 调度中心: 无法连接")
        
        # 节点状态
        try:
            response = requests.get("http://localhost:8000/nodes", timeout=3)
            if response.status_code == 200:
                data = response.json()
                print(f"    ✅ 计算节点: {data.get('total_nodes', 0)} 个")
                print(f"       闲置: {data.get('total_idle', 0)}")
                print(f"       忙碌: {data.get('total_nodes', 0) - data.get('total_idle', 0)}")
        except:
            print(f"    ❌ 节点状态: 无法获取")
        
        # 网页界面状态
        try:
            response = requests.get("http://localhost:8501", timeout=3)
            if response.status_code == 200:
                print(f"    ✅ 网页界面: 运行正常")
            else:
                print(f"    ⚠ 网页界面: HTTP {response.status_code}")
        except:
            print(f"    ❌ 网页界面: 无法连接")
        
        print("\n  ✅ 系统状态检查完成")
        
    except Exception as e:
        print(f"  ❌ 状态检查出错: {e}")

def interactive_demo():
    """交互式演示"""
    print_step("6", "交互式演示")
    
    print("  网页界面功能演示:")
    print("  =========================")
    print("  1. 任务提交页面")
    print("      • 输入Python代码")
    print("      • 配置资源需求")
    print("      • 实时提交任务")
    print()
    print("  2. 任务监控页面")
    print("      • 查看任务历史")
    print("      • 监控执行状态")
    print("      • 查看详细结果")
    print()
    print("  3. 节点管理页面")
    print("      • 查看所有计算节点")
    print("      • 监控节点状态")
    print("      • 查看节点资源")
    print()
    print("  4. 系统统计页面")
    print("      • 性能图表")
    print("      • 使用统计")
    print("      • 实时监控")
    print()
    
    print("  请打开浏览器访问 http://localhost:8501")
    print("  体验完整的网页控制台功能")
    print()
    
    # 等待用户交互
    input("  按回车键继续...")

def cleanup(processes):
    """清理进程"""
    print_step("7", "清理演示环境")
    
    print("  停止所有服务...")
    
    for name, proc in processes.items():
        if proc and proc.poll() is None:  # 进程还在运行
            print(f"    停止 {name}...", end="", flush=True)
            proc.terminate()
            try:
                proc.wait(timeout=3)
                print(" ✓")
            except subprocess.TimeoutExpired:
                print(" ⚠ (强制终止)")
                proc.kill()
    
    print("  演示环境清理完成")

def run_web_demo():
    """运行网页界面演示"""
    print_header("闲置计算加速器 - 网页界面演示")
    print("展示完整的网页控制台功能和用户体验")
    print()
    
    processes = {}
    
    try:
        # 1. 检查前置条件
        if not check_prerequisites():
            print("\n  ❌ 前置条件检查失败")
            return False
        
        # 2. 启动服务
        processes = start_services()
        
        # 3. 打开浏览器
        open_browser()
        
        # 4. 运行演示任务
        run_demo_tasks()
        
        # 5. 显示系统状态
        show_system_status()
        
        # 6. 交互式演示
        interactive_demo()
        
        print_header("演示完成")
        print("✅ 网页界面演示成功完成!")
        print()
        print("演示内容:")
        print("  • 服务启动和监控")
        print("  • 网页界面功能展示")
        print("  • 任务提交和执行")
        print("  • 系统状态监控")
        print()
        print("🎉 网页控制台功能验证通过!")
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n演示被用户中断")
        return False
    except Exception as e:
        print(f"\n演示出错: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 7. 清理
        if processes:
            cleanup(processes)

def main():
    """主函数"""
    success = run_web_demo()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 演示成功!")
        print("\n下一步:")
        print("  1. 继续使用网页界面: streamlit run web_interface.py")
        print("  2. 尝试其他演示: python demo/demo_single_machine.py")
        print("  3. 查看示例任务: python examples/simple_calculation.py")
    else:
        print("❌ 演示失败")
        print("\n故障排除:")
        print("  1. 检查依赖: pip install -r requirements.txt")
        print("  2. 检查端口占用: netstat -an | grep :8000 或 :8501")
        print("  3. 查看日志文件")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

"""
demo/demo_local_network.py
局域网演示脚本 - 精简版
展示基本的分布式计算功能
"""

import os
import sys
import time
import socket
import subprocess
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_step(step, description):
    print(f"\n[{step}] {description}")
    print("-" * 40)

def get_local_ip():
    """获取本地IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def setup_scheduler():
    """设置调度中心"""
    print_step("1", "设置调度中心")
    
    local_ip = get_local_ip()
    print(f"  本地IP: {local_ip}")
    
    # 询问调度中心位置
    print("\n  调度中心位置:")
    print("  1. 本机（默认）")
    print("  2. 其他电脑")
    
    choice = input("  选择 [1]: ").strip()
    
    if choice == "2":
        scheduler_ip = input("  请输入调度中心IP: ").strip()
        if not scheduler_ip:
            scheduler_ip = local_ip
    else:
        scheduler_ip = local_ip
    
    print(f"  调度中心: http://{scheduler_ip}:8000")
    
    # 如果在本机，检查是否运行
    if scheduler_ip == local_ip:
        try:
            response = requests.get(f"http://{scheduler_ip}:8000/", timeout=3)
            if response.status_code == 200:
                print("  ✅ 调度中心已在运行")
            else:
                print("  ⚠ 调度中心未运行")
        except:
            print("  ⚠ 调度中心未运行")
    
    return scheduler_ip

def setup_nodes(scheduler_ip):
    """设置计算节点"""
    print_step("2", "设置计算节点")
    
    print("  节点设置说明:")
    print("  1. 在本机启动节点（演示用）")
    print("  2. 在其他电脑上启动节点")
    print()
    print("  在其他电脑上运行:")
    print(f"    python node/simple_client.py --scheduler http://{scheduler_ip}:8000")
    print()
    
    # 在本机启动一个演示节点
    start_local = input("  在本机启动演示节点？(y/n) [y]: ").strip().lower()
    
    if start_local in ['y', 'yes', '']:
        print("  启动本地演示节点...")
        node_proc = subprocess.Popen(
            [
                sys.executable, "node/simple_client.py",
                "--scheduler", f"http://{scheduler_ip}:8000",
                "--node-name", f"演示节点-{socket.gethostname()}"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print(f"  ✅ 本地节点已启动 (PID: {node_proc.pid})")
        return node_proc
    
    return None

def submit_tasks(scheduler_ip):
    """提交分布式任务"""
    print_step("3", "提交计算任务")
    
    tasks = [
        {
            "name": "计算π值",
            "code": """
# 蒙特卡洛方法计算π
import random

samples = 1000000
inside = 0

for _ in range(samples):
    x = random.random()
    y = random.random()
    if x*x + y*y <= 1.0:
        inside += 1

pi_estimate = 4.0 * inside / samples
print(f"π ≈ {pi_estimate}")
__result__ = pi_estimate
"""
        },
        {
            "name": "数据统计",
            "code": """
# 数据统计分析
import random

data = [random.gauss(100, 15) for _ in range(10000)]

mean = sum(data) / len(data)
variance = sum((x - mean) ** 2 for x in data) / len(data)
std_dev = variance ** 0.5

print(f"数据统计完成")
print(f"均值: {mean:.2f}")
print(f"标准差: {std_dev:.2f}")

__result__ = {"mean": mean, "std_dev": std_dev}
"""
        }
    ]
    
    submitted = []
    
    for task in tasks:
        try:
            payload = {
                "code": task["code"],
                "timeout": 60,
                "resources": {"cpu": 1.0, "memory": 256}
            }
            
            response = requests.post(
                f"http://{scheduler_ip}:8000/submit",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                task_id = response.json().get("task_id")
                submitted.append({"name": task["name"], "id": task_id})
                print(f"  ✅ {task['name']}: 已提交 (ID: {task_id})")
            else:
                print(f"  ❌ {task['name']}: 提交失败")
                
        except Exception as e:
            print(f"  ❌ {task['name']}: 错误 - {e}")
    
    return submitted

def monitor_execution(scheduler_ip, tasks):
    """监控任务执行"""
    print_step("4", "监控执行状态")
    
    if not tasks:
        print("  没有任务需要监控")
        return
    
    print("  任务状态:")
    print("  " + "-" * 50)
    
    completed = 0
    max_wait = 120  # 最多等待2分钟
    start_time = time.time()
    
    try:
        while completed < len(tasks) and (time.time() - start_time) < max_wait:
            # 更新显示
            os.system('cls' if os.name == 'nt' else 'clear')
            print_header("任务执行监控")
            
            for task in tasks:
                try:
                    response = requests.get(
                        f"http://{scheduler_ip}:8000/status/{task['id']}",
                        timeout=3
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        status = data.get("status", "unknown")
                        task["status"] = status
                        
                        if status == "completed" and "result" not in task:
                            task["result"] = data.get("result", "")
                            task["executed_on"] = data.get("executed_on", "未知")
                            completed += 1
                except:
                    pass
                
                # 显示状态
                icon = {
                    "submitted": "🟡",
                    "running": "🔵",
                    "completed": "✅",
                    "failed": "❌"
                }.get(task.get("status", "submitted"), "⚪")
                
                print(f"  {icon} {task['name']:15} {task.get('status', 'submitted'):12}")
                
                if "executed_on" in task:
                    print(f"      执行节点: {task['executed_on']}")
            
            print(f"\n  进度: {completed}/{len(tasks)}")
            print(f"  等待: {int(time.time() - start_time)}秒")
            
            if completed < len(tasks):
                time.sleep(2)
                
    except KeyboardInterrupt:
        print("\n\n监控被中断")
    
    print(f"\n  完成: {completed}/{len(tasks)} 个任务")

def show_results(scheduler_ip):
    """显示结果"""
    print_step("5", "系统状态")
    
    try:
        # 调度中心状态
        response = requests.get(f"http://{scheduler_ip}:8000/", timeout=3)
        if response.status_code == 200:
            data = response.json()
            print(f"  调度中心: {data.get('service', 'N/A')}")
            print(f"    状态: {data.get('status', 'N/A')}")
            print(f"    版本: {data.get('version', 'N/A')}")
        
        # 节点状态
        response = requests.get(f"http://{scheduler_ip}:8000/nodes", timeout=3)
        if response.status_code == 200:
            data = response.json()
            print(f"\n  计算节点: {data.get('total_nodes', 0)} 个")
            if data.get("nodes"):
                for node in data["nodes"][:3]:  # 显示前3个
                    print(f"    • {node.get('node_id')}: {node.get('status')}")
        
        # 任务统计
        response = requests.get(f"http://{scheduler_ip}:8000/stats", timeout=3)
        if response.status_code == 200:
            data = response.json()
            tasks = data.get("tasks", {})
            print(f"\n  任务统计:")
            print(f"    总任务: {tasks.get('total', 0)}")
            print(f"    已完成: {tasks.get('completed', 0)}")
            
    except Exception as e:
        print(f"  获取状态时出错: {e}")

def run_demo():
    """运行演示"""
    print_header("局域网演示 - 分布式计算")
    print("展示在多台电脑上的计算任务分配和执行")
    
    node_proc = None
    
    try:
        # 1. 设置调度中心
        scheduler_ip = setup_scheduler()
        
        # 测试连接
        try:
            requests.get(f"http://{scheduler_ip}:8000/", timeout=5)
            print("  ✅ 连接到调度中心")
        except:
            print(f"\n  ❌ 无法连接到调度中心")
            print(f"  请确保调度中心正在运行: python scheduler/simple_server.py")
            print(f"  或检查网络连接")
            return False
        
        # 2. 设置节点
        node_proc = setup_nodes(scheduler_ip)
        
        # 3. 提交任务
        tasks = submit_tasks(scheduler_ip)
        
        if not tasks:
            print("  没有任务提交成功，演示结束")
            return False
        
        # 4. 监控执行
        monitor_execution(scheduler_ip, tasks)
        
        # 5. 显示结果
        show_results(scheduler_ip)
        
        print_header("演示完成")
        print("✅ 局域网演示成功!")
        print("\n演示了:")
        print("  • 跨电脑任务调度")
        print("  • 分布式计算执行")
        print("  • 实时状态监控")
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n演示被中断")
        return False
    except Exception as e:
        print(f"\n演示出错: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理
        if node_proc and node_proc.poll() is None:
            print("\n停止本地节点...")
            node_proc.terminate()
            try:
                node_proc.wait(timeout=3)
            except:
                node_proc.kill()

def main():
    success = run_demo()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 分布式计算演示完成!")
        print("\n下一步:")
        print("  1. 添加更多电脑作为节点")
        print("  2. 尝试复杂计算任务")
        print("  3. 使用网页界面监控")
    else:
        print("演示完成（部分功能可能未完全展示）")
        print("\n建议:")
        print("  1. 先确保调度中心运行")
        print("  2. 检查网络连接")
        print("  3. 查看日志文件")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

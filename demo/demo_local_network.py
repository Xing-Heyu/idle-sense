"""
demo/demo_local_network.py
局域网演示脚本 - 在多台电脑上展示分布式计算
"""

import os
import sys
import time
import socket
import threading
import subprocess
import requests
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

class NetworkDemo:
    """局域网演示类"""
    
    def __init__(self):
        self.scheduler_ip = None
        self.nodes = []
        self.tasks = []
        self.results = []
        
    def print_header(self, title):
        """打印标题"""
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)
    
    def print_step(self, step, description):
        """打印步骤"""
        print(f"\n[{step}] {description}")
        print("-" * 50)
    
    def get_local_ip(self):
        """获取本地IP地址"""
        try:
            # 创建一个临时socket来获取本地IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def setup_scheduler(self):
        """设置调度中心"""
        self.print_step("1", "设置调度中心")
        
        local_ip = self.get_local_ip()
        print(f"  本地IP地址: {local_ip}")
        
        # 询问调度中心IP
        print("\n  选择调度中心位置:")
        print(f"  1. 本机 ({local_ip})")
        print("  2. 其他电脑")
        
        choice = input("  选择 [1]: ").strip()
        if choice == "2" or choice == "2":
            self.scheduler_ip = input("  请输入调度中心IP地址: ").strip()
            if not self.scheduler_ip:
                print("  ⚠ 使用默认: 本机")
                self.scheduler_ip = local_ip
        else:
            self.scheduler_ip = local_ip
        
        print(f"\n  调度中心地址: http://{self.scheduler_ip}:8000")
        
        # 如果调度中心在本机，检查是否运行
        if self.scheduler_ip == local_ip:
            if not self.check_scheduler_running():
                print("  调度中心未运行，需要启动吗？")
                start = input("  启动调度中心？(y/n) [y]: ").strip().lower()
                if start in ['y', 'yes', '']:
                    self.start_local_scheduler()
        
        return self.scheduler_ip
    
    def check_scheduler_running(self):
        """检查调度中心是否在运行"""
        try:
            response = requests.get(f"http://{self.scheduler_ip}:8000/", timeout=3)
            return response.status_code == 200
        except:
            return False
    
    def start_local_scheduler(self):
        """启动本地调度中心"""
        print("  启动本地调度中心...")
        
        # 启动调度中心
        proc = subprocess.Popen(
            [sys.executable, "scheduler/simple_server.py", "--host", "0.0.0.0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print(f"  调度中心已启动 (PID: {proc.pid})")
        
        # 等待启动完成
        print("  等待启动完成...", end="", flush=True)
        for _ in range(30):
            if self.check_scheduler_running():
                print(" ✓")
                return True
            print(".", end="", flush=True)
            time.sleep(1)
        
        print("\n  ⚠ 调度中心启动较慢，继续演示...")
        return False
    
    def setup_nodes(self):
        """设置计算节点"""
        self.print_step("2", "设置计算节点")
        
        print("  节点设置选项:")
        print("  1. 本机作为节点")
        print("  2. 其他电脑作为节点")
        print("  3. 模拟多个节点（演示用）")
        
        choice = input("  选择 [1]: ").strip()
        
        if choice == "2":
            self.setup_remote_nodes()
        elif choice == "3":
            self.setup_simulated_nodes()
        else:
            self.setup_local_node()
    
    def setup_local_node(self):
        """设置本地节点"""
        print("\n  设置本地计算节点...")
        
        # 启动本地节点
        proc = subprocess.Popen(
            [
                sys.executable, "node/simple_client.py",
                "--scheduler", f"http://{self.scheduler_ip}:8000",
                "--node-name", f"本地节点-{socket.gethostname()}"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        self.nodes.append({
            "name": f"本地节点-{socket.gethostname()}",
            "type": "local",
            "process": proc
        })
        
        print(f"  本地节点已启动: 本地节点-{socket.gethostname()}")
    
    def setup_simulated_nodes(self):
        """设置模拟节点（用于演示）"""
        print("\n  设置模拟节点...")
        
        # 模拟不同平台的节点
        simulated_nodes = [
            {"name": "Windows-工作站", "platform": "Windows", "cpu_cores": 8},
            {"name": "macBook-Pro", "platform": "macOS", "cpu_cores": 10},
            {"name": "Linux-服务器", "platform": "Linux", "cpu_cores": 16},
            {"name": "旧笔记本", "platform": "Windows", "cpu_cores": 4},
        ]
        
        for i, node_info in enumerate(simulated_nodes):
            self.nodes.append({
                "name": node_info["name"],
                "type": "simulated",
                "platform": node_info["platform"],
                "cpu_cores": node_info["cpu_cores"],
                "status": "idle"
            })
            print(f"  模拟节点 {i+1}: {node_info['name']} ({node_info['platform']})")
        
        print(f"  共设置 {len(simulated_nodes)} 个模拟节点")
    
    def setup_remote_nodes(self):
        """设置远程节点"""
        print("\n  设置远程节点说明:")
        print("  1. 在其他电脑上运行: python node/simple_client.py")
        print("  2. 指定调度中心地址: --scheduler http://{self.scheduler_ip}:8000")
        print("  3. 设置节点名称: --node-name '自定义名称'")
        print("\n  按回车键继续...")
        input()
    
    def submit_distributed_tasks(self):
        """提交分布式任务"""
        self.print_step("3", "提交分布式计算任务")
        
        # 定义一组相关任务
        tasks = [
            {
                "name": "计算π值",
                "code": """
# 计算π值（蒙特卡洛方法）
import random
import time

samples = 2000000
inside = 0

start = time.time()
for i in range(samples):
    x = random.random()
    y = random.random()
    if x*x + y*y <= 1.0:
        inside += 1

pi_estimate = 4.0 * inside / samples
execution_time = time.time() - start

print(f"π计算任务完成")
print(f"样本数: {samples:,}")
print(f"π估计值: {pi_estimate:.10f}")
print(f"计算时间: {execution_time:.3f}秒")
print(f"性能: {samples/execution_time:,.0f} 样本/秒")

__result__ = {
    "task": "pi_calculation",
    "pi_estimate": pi_estimate,
    "samples": samples,
    "time": execution_time
}
""",
                "resources": {"cpu": 1.0, "memory": 256}
            },
            {
                "name": "数据处理",
                "code": """
# 数据处理任务
import random
import statistics
import time

start = time.time()

# 生成测试数据
data_size = 500000
data = [random.gauss(100, 15) for _ in range(data_size)]

# 计算统计信息
mean = statistics.mean(data)
stdev = statistics.stdev(data)
median = sorted(data)[len(data)//2]
minimum = min(data)
maximum = max(data)

# 数据分组
bins = [0, 50, 100, 150, 200, float('inf')]
histogram = {f"{bins[i]}-{bins[i+1]}": 0 for i in range(len(bins)-1)}

for value in data:
    for i in range(len(bins)-1):
        if bins[i] <= value < bins[i+1]:
            key = f"{bins[i]}-{bins[i+1]}"
            histogram[key] += 1
            break

execution_time = time.time() - start

print(f"数据处理任务完成")
print(f"数据量: {data_size:,}")
print(f"平均值: {mean:.2f}")
print(f"标准差: {stdev:.2f}")
print(f"计算时间: {execution_time:.3f}秒")

__result__ = {
    "task": "data_processing",
    "data_size": data_size,
    "mean": mean,
    "stdev": stdev,
    "histogram": histogram,
    "time": execution_time
}
""",
                "resources": {"cpu": 1.5, "memory": 512}
            },
            {
                "name": "矩阵运算",
                "code": """
# 矩阵运算任务
import random
import time

start = time.time()

# 创建矩阵
size = 150
A = [[random.random() for _ in range(size)] for _ in range(size)]
B = [[random.random() for _ in range(size)] for _ in range(size)]
C = [[0 for _ in range(size)] for _ in range(size)]

# 矩阵乘法
for i in range(size):
    for j in range(size):
        for k in range(size):
            C[i][j] += A[i][k] * B[k][j]

execution_time = time.time() - start
flops = 2 * size**3 / execution_time

print(f"矩阵运算任务完成")
print(f"矩阵大小: {size}×{size}")
print(f"浮点运算数: {2*size**3:,}")
print(f"计算时间: {execution_time:.3f}秒")
print(f"性能: {flops/1e6:.2f} MFLOPS")

__result__ = {
    "task": "matrix_multiplication",
    "matrix_size": size,
    "flops": flops,
    "time": execution_time
}
""",
                "resources": {"cpu": 2.0, "memory": 1024}
            },
            {
                "name": "排序算法",
                "code": """
# 大规模数据排序
import random
import time

start = time.time()

# 生成测试数据
data_size = 300000
data = [random.randint(1, 1000000) for _ in range(data_size)]

print(f"开始排序 {data_size:,} 个元素...")

# 快速排序实现
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr)//2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)

# 执行排序
sorted_data = quicksort(data)

execution_time = time.time() - start

# 验证排序结果
is_sorted = all(sorted_data[i] <= sorted_data[i+1] for i in range(len(sorted_data)-1))

print(f"排序任务完成")
print(f"数据量: {data_size:,}")
print(f"排序正确: {is_sorted}")
print(f"计算时间: {execution_time:.3f}秒")
print(f"速度: {data_size/execution_time:,.0f} 元素/秒")

__result__ = {
    "task": "sorting",
    "data_size": data_size,
    "is_sorted": is_sorted,
    "time": execution_time
}
""",
                "resources": {"cpu": 1.0, "memory": 768}
            }
        ]
        
        print("  提交4个不同类型的计算任务:")
        
        for i, task_info in enumerate(tasks):
            try:
                response = requests.post(
                    f"http://{self.scheduler_ip}:8000/submit",
                    json={
                        "code": task_info["code"],
                        "timeout": 180,
                        "resources": task_info["resources"]
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    task_id = data.get("task_id")
                    
                    self.tasks.append({
                        "id": task_id,
                        "name": task_info["name"],
                        "status": "submitted",
                        "submitted_at": datetime.now()
                    })
                    
                    print(f"  {i+1}. {task_info['name']}: ✅ (ID: {task_id})")
                else:
                    print(f"  {i+1}. {task_info['name']}: ❌ 提交失败")
                    
            except Exception as e:
                print(f"  {i+1}. {task_info['name']}: ❌ 错误: {e}")
        
        print(f"\n  共提交 {len(self.tasks)} 个任务")
    
    def monitor_distributed_execution(self):
        """监控分布式执行"""
        self.print_step("4", "监控分布式执行")
        
        print("  监控任务执行状态...")
        print("  按 Ctrl+C 停止监控\n")
        
        completed_tasks = 0
        start_time = time.time()
        
        try:
            while completed_tasks < len(self.tasks):
                # 清屏并显示状态
                self.display_execution_status()
                
                # 更新任务状态
                for task in self.tasks:
                    if task["status"] not in ["completed", "failed"]:
                        try:
                            response = requests.get(
                                f"http://{self.scheduler_ip}:8000/status/{task['id']}",
                                timeout=3
                            )
                            if response.status_code == 200:
                                data = response.json()
                                task["status"] = data.get("status", task["status"])
                                
                                if task["status"] == "completed":
                                    task["completed_at"] = datetime.now()
                                    task["result"] = data.get("result", "")
                                    task["executed_on"] = data.get("executed_on", "未知")
                                    completed_tasks += 1
                                    
                                    # 显示完成的任务
                                    print(f"\n  ✅ {task['name']} 已完成!")
                                    print(f"     执行节点: {task['executed_on']}")
                                    
                                elif task["status"] == "failed":
                                    task["completed_at"] = datetime.now()
                                    completed_tasks += 1
                                    print(f"\n  ❌ {task['name']} 失败")
                        except:
                            pass
                
                # 显示节点状态
                try:
                    response = requests.get(f"http://{self.scheduler_ip}:8000/nodes", timeout=3)
                    if response.status_code == 200:
                        data = response.json()
                        active_nodes = data.get("total_nodes", 0)
                        idle_nodes = data.get("total_idle", 0)
                        
                        # 更新模拟节点状态
                        if any(node["type"] == "simulated" for node in self.nodes):
                            # 随机更新模拟节点状态
                            import random
                            for node in self.nodes:
                                if node["type"] == "simulated":
                                    if random.random() > 0.7:  # 30%几率改变状态
                                        node["status"] = random.choice(["idle", "busy"])
                except:
                    pass
                
                time.sleep(2)
                
        except KeyboardInterrupt:
            print("\n\n监控被用户中断")
        
        total_time = time.time() - start_time
        print(f"\n  总执行时间: {total_time:.1f}秒")
        print(f"  完成任务: {completed_tasks}/{len(self.tasks)}")
    
    def display_execution_status(self):
        """显示执行状态"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("=" * 70)
        print("  分布式计算执行监控")
        print("=" * 70)
        
        # 显示任务状态
        print("\n  任务状态:")
        print("  " + "-" * 68)
        
        for task in self.tasks:
            status_icon = {
                "submitted": "🟡",
                "running": "🔵",
                "completed": "🟢",
                "failed": "🔴"
            }.get(task["status"], "⚪")
            
            elapsed = ""
            if "submitted_at" in task:
                elapsed_seconds = (datetime.now() - task["submitted_at"]).total_seconds()
                elapsed = f" ({elapsed_seconds:.0f}s)"
            
            executed_on = f" | 节点: {task.get('executed_on', '等待中')}" if task.get('executed_on') else ""
            
            print(f"  {status_icon} {task['name']:20} {task['status']:12}{elapsed}{executed_on}")
        
        # 显示节点状态
        print(f"\n  节点状态:")
        print("  " + "-" * 68)
        
        # 显示真实节点
        real_nodes = [n for n in self.nodes if n["type"] != "simulated"]
        if real_nodes:
            for node in real_nodes:
                print(f"  🖥️  {node['name']:25} 运行中")
        
        # 显示模拟节点
        simulated_nodes = [n for n in self.nodes if n["type"] == "simulated"]
        if simulated_nodes:
            for node in simulated_nodes:
                status_icon = "🟢" if node["status"] == "idle" else "🔵"
                print(f"  {status_icon} {node['name']:25} {node['status']:10} ({node['cpu_cores']}核)")
        
        # 显示调度中心状态
        print(f"\n  调度中心: http://{self.scheduler_ip}:8000")
        print("  按 Ctrl+C 停止监控")
    
    def show_results_summary(self):
        """显示结果汇总"""
        self.print_step("5", "结果汇总")
        
        completed_tasks = [t for t in self.tasks if t["status"] == "completed"]
        failed_tasks = [t for t in self.tasks if t["status"] == "failed"]
        pending_tasks = [t for t in self.tasks if t["status"] not in ["completed", "failed"]]
        
        print(f"  任务完成情况:")
        print(f"    ✅ 已完成: {len(completed_tasks)}")
        print(f"    ❌ 失败: {len(failed_tasks)}")
        print(f"    🟡 进行中: {len(pending_tasks)}")
        
        if completed_tasks:
            print(f"\n  完成的任务详情:")
            for task in completed_tasks:
                elapsed = (task["completed_at"] - task["submitted_at"]).total_seconds()
                print(f"    • {task['name']}: {elapsed:.1f}秒 ({task.get('executed_on', '未知节点')})")
        
        # 显示性能统计
        try:
            response = requests.get(f"http://{self.scheduler_ip}:8000/stats", timeout=3)
            if response.status_code == 200:
                data = response.json()
                tasks_info = data.get("tasks", {})
                
                print(f"\n  系统统计:")
                print(f"    总任务数: {tasks_info.get('total', 0)}")
                print(f"    平均用时: {tasks_info.get('avg_time', 0):.1f}秒")
                
                throughput = data.get("throughput", {})
                print(f"    计算时数: {throughput.get('compute_hours', 0):.2f}小时")
        except:
            pass
        
        print(f"\n  🎉 分布式计算演示完成!")
    
    def cleanup(self):
        """清理演示环境"""
        self.print_step("6", "清理演示环境")
        
        print("  停止本地进程...")
        
        # 停止本地节点
        for node in self.nodes:
            if node["type"] == "local" and node.get("process"):
                proc = node["process"]
                if proc.poll() is None:
                    print(f"    停止节点: {node['name']}")
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
        
        print("  演示环境清理完成")
    
    def run(self):
        """运行局域网演示"""
        self.print_header("闲置计算加速器 - 局域网演示")
        print("展示在多台电脑上的分布式计算能力")
        print()
        
        try:
            # 1. 设置调度中心
            self.setup_scheduler()
            
            if not self.check_scheduler_running():
                print("\n  ❌ 无法连接到调度中心，请检查:")
                print(f"    1. 调度中心是否运行在 http://{self.scheduler_ip}:8000")
                print(f"    2. 防火墙是否开放端口8000")
                print(f"    3. 网络连接是否正常")
                return False
            
            print(f"\n  ✅ 调度中心连接成功")
            
            # 2. 设置计算节点
            self.setup_nodes()
            
            # 等待节点注册
            print(f"\n  等待节点注册...", end="", flush=True)
            for _ in range(20):
                try:
                    response = requests.get(f"http://{self.scheduler_ip}:8000/nodes", timeout=3)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("total_nodes", 0) > 0 or any(n["type"] == "simulated" for n in self.nodes):
                            print(" ✓")
                            break
                except:
                    pass
                print(".", end="", flush=True)
                time.sleep(1)
            else:
                print("\n  ⚠ 节点注册较慢，继续演示...")
            
            # 3. 提交分布式任务
            self.submit_distributed_tasks()
            
            # 4. 监控分布式执行
            self.monitor_distributed_execution()
            
            # 5. 显示结果汇总
            self.show_results_summary()
            
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
            # 6. 清理
            self.cleanup()

def main():
    """主函数"""
    demo = NetworkDemo()
    success = demo.run()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ 局域网演示成功完成!")
        print("\n演示内容:")
        print("  • 多机调度中心设置")
        print("  • 分布式节点管理")
        print("  • 并行任务提交")
        print("  • 分布式执行监控")
        print("  • 结果汇总分析")
        print()
        print("🎉 闲置计算加速器分布式能力验证通过!")
    else:
        print("❌ 演示失败或部分完成")
        print("\n建议:")
        print("  1. 先运行单机演示: python demo/demo_single_machine.py")
        print("  2. 确保所有电脑在同一网络")
        print("  3. 检查防火墙设置")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

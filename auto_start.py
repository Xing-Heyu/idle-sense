#!/usr/bin/env python3
"""
闲置计算加速器 - 自动启动脚本（增强版）
一键启动调度中心、节点客户端和网页界面
支持自动平台检测，选择最优客户端实现
"""

import subprocess
import sys
import time
import threading
import os
import platform
from pathlib import Path
import argparse

def run_command(command, name, delay=0):
    """运行命令并监控输出"""
    print(f"🚀 启动 {name}...")
    time.sleep(delay)
    
    try:
        if sys.platform == "win32":
            # Windows系统
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
        else:
            # Linux/Mac系统
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                shell=True
            )
        
        # 实时输出
        def output_reader():
            for line in iter(process.stdout.readline, ''):
                print(f"[{name}] {line.rstrip()}")
        
        output_thread = threading.Thread(target=output_reader)
        output_thread.daemon = True
        output_thread.start()
        
        return process
    except Exception as e:
        print(f"❌ 启动 {name} 失败: {e}")
        return None

def check_scheduler_health(scheduler_url="http://localhost:8000"):
    """检查调度中心是否健康"""
    try:
        import requests
    except ImportError:
        print("❌ 缺少requests库，请先安装依赖: pip install -r requirements.txt")
        return False
    
    max_retries = 10
    for i in range(max_retries):
        try:
            response = requests.get(scheduler_url, timeout=5)
            if response.status_code == 200:
                print("✅ 调度中心健康检查通过")
                return True
        except Exception as e:
            print(f"⏳ 等待调度中心启动... ({i+1}/{max_retries}) - {str(e)[:50]}...")
        
        time.sleep(2)
    
    print("❌ 调度中心启动超时")
    return False

def get_platform_client():
    """
    自动检测平台并返回最优客户端实现
    """
    system = platform.system()
    if system == "Windows":
        return "node/windows_client.py", "Windows节点客户端"
    elif system == "Darwin":
        return "node/simple_client.py", "macOS节点客户端"
    elif system == "Linux":
        return "node/simple_client.py", "Linux节点客户端"
    else:
        return "node/simple_client.py", "通用节点客户端"

def check_dependencies():
    """检查必要的依赖"""
    print("🔍 检查依赖...")
    
    required_modules = ["requests", "fastapi", "uvicorn", "streamlit"]
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module} 已安装")
        except ImportError:
            missing_modules.append(module)
            print(f"❌ {module} 未安装")
    
    if missing_modules:
        print("\n💡 建议安装缺少的依赖:")
        print(f"pip install {' '.join(missing_modules)}")
        print("或运行: pip install -r requirements.txt")
        # 继续运行，因为用户可能已经在其他环境中安装了依赖
    
    return True

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="闲置计算加速器一键启动脚本")
    parser.add_argument("--scheduler-port", type=int, default=8000, help="调度中心端口")
    parser.add_argument("--web-port", type=int, default=8501, help="网页界面端口")
    parser.add_argument("--no-web", action="store_true", help="不启动网页界面")
    parser.add_argument("--no-node", action="store_true", help="不启动节点客户端")
    args = parser.parse_args()
    
    print("=" * 60)
    print("⚡ 闲置计算加速器 - 自动启动脚本（增强版）")
    print("=" * 60)
    
    # 切换到项目目录
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    print(f"📁 项目目录: {project_dir}")
    
    # 检查环境
    print(f"🐍 Python版本: {sys.version}")
    print(f"💻 操作系统: {platform.system()}")
    
    # 检查依赖
    check_dependencies()
    
    # 自动检测平台并选择最优客户端
    client_file, client_name = get_platform_client()
    print(f"🔍 自动选择: {client_name}")
    
    # 构建启动命令
    scheduler_url = f"http://localhost:{args.scheduler_port}"
    scheduler_cmd = f"python scheduler/simple_server.py"
    if args.scheduler_port != 8000:
        scheduler_cmd += f" --port {args.scheduler_port}"
    
    web_cmd = f"streamlit run web_interface.py --server.port {args.web_port}"
    
    # 启动调度中心
    scheduler_process = run_command(scheduler_cmd, "调度中心")
    
    # 等待调度中心启动
    if not check_scheduler_health(scheduler_url):
        print("❌ 调度中心启动失败，请检查错误信息")
        if scheduler_process:
            scheduler_process.terminate()
        return
    
    # 启动节点客户端（根据平台自动选择）
    node_process = None
    if not args.no_node:
        time.sleep(2)
        node_process = run_command(f"python {client_file}", client_name)
    
    # 启动网页界面
    web_process = None
    if not args.no_web:
        time.sleep(3)
        web_process = run_command(web_cmd, "网页界面")
    
    print("\n" + "=" * 60)
    print("🎉 所有组件启动完成！")
    print("=" * 60)
    print("\n📊 服务状态:")
    print(f"  • 调度中心: {scheduler_url}")
    if not args.no_web:
        print(f"  • 网页界面: http://localhost:{args.web_port}")
    if not args.no_node:
        print(f"  • {client_name}: 正在运行")
    print("\n💡 使用说明:")
    if not args.no_web:
        print(f"  1. 打开浏览器访问 http://localhost:{args.web_port}")
        print("  2. 在网页界面提交计算任务")
    if not args.no_node:
        print(f"  3. {client_name}会自动执行任务")
    print("  4. 按 Ctrl+C 停止所有服务")
    print("\n" + "=" * 60)
    
    try:
        # 保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 收到停止信号，正在关闭所有服务...")
        
        # 终止所有进程
        processes = []
        if web_process:
            processes.append(("网页界面", web_process))
        if node_process:
            processes.append((client_name, node_process))
        if scheduler_process:
            processes.append(("调度中心", scheduler_process))
        
        for name, process in processes:
            if process:
                print(f"正在停止 {name}...")
                try:
                    process.terminate()
                    process.wait(timeout=5)
                    print(f"✅ {name} 已停止")
                except subprocess.TimeoutExpired:
                    print(f"⚠️  {name} 停止超时，强制终止")
                    process.kill()
                except Exception as e:
                    print(f"❌ 停止 {name} 时出错: {e}")
        
        print("✅ 所有服务已停止")

if __name__ == "__main__":
    main()
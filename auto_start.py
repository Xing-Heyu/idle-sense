#!/usr/bin/env python3
"""
闲置计算加速器 - 自动启动脚本
一键启动调度中心、节点客户端和网页界面
"""

import subprocess
import sys
import time
import threading
import os
from pathlib import Path

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
                universal_newlines=True
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

def check_scheduler_health():
    """检查调度中心是否健康"""
    import requests
    
    max_retries = 10
    for i in range(max_retries):
        try:
            response = requests.get("http://localhost:8000/", timeout=5)
            if response.status_code == 200:
                print("✅ 调度中心健康检查通过")
                return True
        except:
            pass
        
        print(f"⏳ 等待调度中心启动... ({i+1}/{max_retries})")
        time.sleep(2)
    
    print("❌ 调度中心启动超时")
    return False

def main():
    """主函数"""
    print("=" * 60)
    print("⚡ 闲置计算加速器 - 自动启动脚本")
    print("=" * 60)
    
    # 切换到项目目录
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    print(f"📁 项目目录: {project_dir}")
    
    # 检查Python环境
    print(f"🐍 Python版本: {sys.version}")
    
    # 启动调度中心
    scheduler_process = run_command("python scheduler/simple_server.py", "调度中心")
    
    # 等待调度中心启动
    if not check_scheduler_health():
        print("❌ 调度中心启动失败，请检查错误信息")
        if scheduler_process:
            scheduler_process.terminate()
        return
    
    # 启动节点客户端
    time.sleep(2)
    node_process = run_command("python node/simple_client.py", "节点客户端")
    
    # 启动网页界面
    time.sleep(3)
    web_process = run_command("streamlit run web_interface.py", "网页界面")
    
    print("\n" + "=" * 60)
    print("🎉 所有组件启动完成！")
    print("=" * 60)
    print("\n📊 服务状态:")
    print("  • 调度中心: http://localhost:8000")
    print("  • 网页界面: http://localhost:8501")
    print("  • 节点客户端: 正在运行")
    print("\n💡 使用说明:")
    print("  1. 打开浏览器访问 http://localhost:8501")
    print("  2. 在网页界面提交计算任务")
    print("  3. 节点客户端会自动执行任务")
    print("  4. 按 Ctrl+C 停止所有服务")
    print("\n" + "=" * 60)
    
    try:
        # 保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 收到停止信号，正在关闭所有服务...")
        
        # 终止所有进程
        for name, process in [("网页界面", web_process), ("节点客户端", node_process), ("调度中心", scheduler_process)]:
            if process:
                print(f"正在停止 {name}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        
        print("✅ 所有服务已停止")

if __name__ == "__main__":
    main()
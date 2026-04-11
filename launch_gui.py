"""
Idle-Sense 图形化启动器
零配置启动分布式算力共享平台
对等个人中心架构 - 本地完整栈 + 调度器互联
"""

import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk
except ImportError:
    print("请安装 Python 时勾选 tcl/tk 选项")
    sys.exit(1)


class IdleSenseLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Idle-Sense 对等个人中心")
        self.root.geometry("600x550")
        self.root.resizable(False, False)

        self.scheduler_process = None
        self.node_process = None
        self.is_running = False

        self._setup_ui()
        self._check_environment()

    def _setup_ui(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Microsoft YaHei", 16, "bold"))
        style.configure("Status.TLabel", font=("Microsoft YaHei", 10))
        style.configure("Big.TButton", font=("Microsoft YaHei", 12), padding=15)

        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(
            main_frame, text="🚀 Idle-Sense 对等个人中心", style="Title.TLabel"
        )
        title_label.pack(pady=(0, 5))

        subtitle = ttk.Label(
            main_frame, text="Peer-to-Peer Personal Center", font=("Microsoft YaHei", 10)
        )
        subtitle.pack(pady=(0, 15))

        arch_frame = ttk.LabelFrame(main_frame, text="架构说明", padding=10)
        arch_frame.pack(fill=tk.X, pady=(0, 15))

        arch_text = """本地运行: 调度器 + 节点 + Web界面
联邦互联: 自动发现其他调度器
任务共享: 本地无空闲节点时自动转发"""
        
        ttk.Label(
            arch_frame,
            text=arch_text,
            font=("Microsoft YaHei", 9),
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        self.status_label = ttk.Label(main_frame, text="● 检测环境中...", style="Status.TLabel")
        self.status_label.pack(pady=(0, 15))

        self.start_btn = ttk.Button(
            main_frame,
            text="🚀 一键启动",
            style="Big.TButton",
            command=self.toggle_federated,
        )
        self.start_btn.pack(fill=tk.X, pady=(0, 15))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            btn_frame, text="🌐 打开 Web 界面", style="Big.TButton", command=self.open_web
        ).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        ttk.Button(
            btn_frame, text="📊 查看状态", style="Big.TButton", command=self.show_status
        ).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        log_frame = ttk.LabelFrame(main_frame, text="运行日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=10)

        ttk.Button(bottom_frame, text="安装依赖", command=self.install_deps).pack(
            side=tk.LEFT, padx=5
        )

        ttk.Button(bottom_frame, text="使用帮助", command=self.show_help).pack(side=tk.LEFT, padx=5)

        ttk.Button(bottom_frame, text="退出", command=self.on_closing).pack(side=tk.RIGHT, padx=5)

    def _check_environment(self):
        python_ok = sys.version_info >= (3, 9)
        venv_exists = Path("venv").exists()

        if python_ok:
            if venv_exists:
                self.status_label.config(text="● 环境就绪，点击按钮启动")
            else:
                self.status_label.config(text="● 请先点击'安装依赖'")
        else:
            self.status_label.config(text="● 需要 Python 3.9+")
            messagebox.showwarning(
                "环境警告", "需要 Python 3.9 或更高版本\n当前版本: " + sys.version.split()[0]
            )

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def toggle_federated(self):
        if self.is_running:
            self.stop_federated()
        else:
            self.start_federated()

    def start_federated(self):
        self.log("正在启动对等个人中心...")

        venv_python = Path("venv/Scripts/python.exe")
        python_exe = str(venv_python) if venv_python.exists() else sys.executable

        env = os.environ.copy()
        env["ENABLE_FEDERATION"] = "true"
        env["FEDERATION_PORT"] = "8765"
        env["PORT"] = "8000"

        try:
            self.scheduler_process = subprocess.Popen(
                [python_exe, "-m", "legacy.scheduler.simple_server"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )

            self.log("调度器已启动（联邦模式）: http://localhost:8000")
            self.log("联邦端口: 8765")

            threading.Thread(
                target=self._read_output, args=(self.scheduler_process,), daemon=True
            ).start()

            import time
            time.sleep(2)

            self.node_process = subprocess.Popen(
                [python_exe, "-m", "legacy.node.simple_client", "--scheduler-url", "http://localhost:8000"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            self.log("本地节点已启动并连接到调度器")

            threading.Thread(
                target=self._read_output, args=(self.node_process,), daemon=True
            ).start()

            self.is_running = True
            self.start_btn.config(text="⏹️ 停止服务")
            self.status_label.config(text="● 运行中")
            
            self.log("")
            self.log("=" * 50)
            self.log("对等个人中心已启动!")
            self.log("=" * 50)
            self.log("本地服务:")
            self.log("  - Web界面: http://localhost:8501")
            self.log("  - API文档: http://localhost:8000/docs")
            self.log("  - 联邦状态: http://localhost:8000/api/federation/stats")
            self.log("")
            self.log("其他用户连接方式:")
            self.log("  1. 确保网络互通（同一局域网或公网）")
            self.log("  2. 对方运行相同的启动脚本")
            self.log("  3. 调度器将自动发现并连接")
            self.log("=" * 50)

        except Exception as e:
            self.log(f"启动失败: {e}")
            messagebox.showerror("错误", f"启动失败:\n{e}")

    def stop_federated(self):
        if self.scheduler_process:
            self.scheduler_process.terminate()
            self.scheduler_process = None
        if self.node_process:
            self.node_process.terminate()
            self.node_process = None
        
        self.is_running = False
        self.start_btn.config(text="🚀 一键启动")
        self.status_label.config(text="● 已停止")
        self.log("服务已停止")

    def _read_output(self, process):
        try:
            for line in iter(process.stdout.readline, ""):
                if line:
                    self.log(line.strip())
        except Exception as e:
            self.log(f"读取输出异常: {e}")

    def open_web(self):
        try:
            webbrowser.open("http://localhost:8501")
            self.log("已打开 Web 界面")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开浏览器:\n{e}")

    def show_status(self):
        try:
            import requests

            try:
                fed_response = requests.get("http://localhost:8000/api/federation/stats", timeout=2)
                if fed_response.status_code == 200:
                    fed_stats = fed_response.json()
                    msg = f"""联邦系统状态

本地调度器:
  ID: {fed_stats.get('scheduler_id', 'N/A')}

联邦网络:
  远程调度器: {fed_stats.get('remote_schedulers', 0)}
  已连接: {fed_stats.get('connected_schedulers', 0)}
  远程节点: {fed_stats.get('total_remote_nodes', 0)}

任务统计:
  转发任务: {fed_stats.get('stats', {}).get('tasks_forwarded', 0)}
  接收任务: {fed_stats.get('stats', {}).get('tasks_received', 0)}
  返回结果: {fed_stats.get('stats', {}).get('results_returned', 0)}
"""
                    messagebox.showinfo("联邦系统状态", msg)
                    return
            except Exception:
                pass

            response = requests.get("http://localhost:8000/stats", timeout=2)
            if response.status_code == 200:
                stats = response.json()
                msg = f"""系统状态

任务统计:
  总任务数: {stats.get('tasks', {}).get('total', 0)}
  等待中: {stats.get('tasks', {}).get('pending', 0)}
  运行中: {stats.get('tasks', {}).get('assigned', 0)}
  已完成: {stats.get('tasks', {}).get('completed', 0)}

节点统计:
  总节点数: {stats.get('nodes', {}).get('total', 0)}
  在线节点: {stats.get('nodes', {}).get('online', 0)}
  可用节点: {stats.get('nodes', {}).get('available', 0)}
"""
                messagebox.showinfo("系统状态", msg)
            else:
                messagebox.showwarning("警告", "调度器未响应")
        except Exception as e:
            messagebox.showwarning("警告", f"无法连接调度器\n请先启动服务\n错误: {e}")

    def install_deps(self):
        self.log("正在安装依赖...")

        try:
            if not Path("venv").exists():
                subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
                self.log("虚拟环境创建成功")

            venv_python = Path("venv/Scripts/python.exe")
            python_exe = str(venv_python) if venv_python.exists() else sys.executable

            subprocess.run([python_exe, "-m", "pip", "install", "--upgrade", "pip"], check=True)
            subprocess.run(
                [python_exe, "-m", "pip", "install", "-r", "requirements.txt"], check=True
            )
            subprocess.run([python_exe, "-m", "pip", "install", "wasmtime"], check=True)

            self.log("依赖安装完成！")
            self.status_label.config(text="● 环境就绪，点击按钮启动")
            messagebox.showinfo("成功", "依赖安装完成！")

        except Exception as e:
            self.log(f"安装失败: {e}")
            messagebox.showerror("错误", f"安装失败:\n{e}")

    def show_help(self):
        help_text = """使用说明

1. 首次使用:
   - 点击"安装依赖"按钮
   - 等待安装完成

2. 启动服务:
   - 点击"一键启动"按钮
   - 自动启动调度器 + 节点 + 联邦模块
   - 打开 Web 界面管理任务

3. 联邦网络:
   - 其他用户运行相同的启动脚本
   - 调度器自动发现并连接
   - 形成去中心化算力联盟

4. 访问地址:
   - Web界面: http://localhost:8501
   - API文档: http://localhost:8000/docs
   - 联邦状态: http://localhost:8000/api/federation/stats

5. 命令行任务提交:
   python -m legacy.cli task submit --code "代码"

更多信息请查看 README.md
"""
        messagebox.showinfo("使用帮助", help_text)

    def on_closing(self):
        if self.scheduler_process:
            self.scheduler_process.terminate()
        if self.node_process:
            self.node_process.terminate()
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


if __name__ == "__main__":
    app = IdleSenseLauncher()
    app.run()

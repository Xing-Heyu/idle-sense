"""
Idle-Sense 图形化启动器
零配置启动分布式算力共享平台
"""

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
        self.root.title("Idle-Sense 分布式算力共享平台")
        self.root.geometry("600x500")
        self.root.resizable(False, False)

        self.scheduler_process = None
        self.node_process = None

        self._setup_ui()
        self._check_environment()

    def _setup_ui(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Microsoft YaHei", 16, "bold"))
        style.configure("Status.TLabel", font=("Microsoft YaHei", 10))
        style.configure("Big.TButton", font=("Microsoft YaHei", 11), padding=10)

        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(
            main_frame,
            text="🚀 Idle-Sense 分布式算力共享平台",
            style="Title.TLabel"
        )
        title_label.pack(pady=(0, 10))

        subtitle = ttk.Label(
            main_frame,
            text="一键启动，共享闲置算力",
            font=("Microsoft YaHei", 10)
        )
        subtitle.pack(pady=(0, 20))

        self.status_label = ttk.Label(
            main_frame,
            text="● 检测环境中...",
            style="Status.TLabel"
        )
        self.status_label.pack(pady=(0, 20))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        self.scheduler_btn = ttk.Button(
            btn_frame,
            text="🖥️ 启动调度器",
            style="Big.TButton",
            command=self.toggle_scheduler
        )
        self.scheduler_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        self.node_btn = ttk.Button(
            btn_frame,
            text="💻 启动节点",
            style="Big.TButton",
            command=self.start_node
        )
        self.node_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        btn_frame2 = ttk.Frame(main_frame)
        btn_frame2.pack(fill=tk.X, pady=10)

        ttk.Button(
            btn_frame2,
            text="🌐 打开 Web 界面",
            style="Big.TButton",
            command=self.open_web
        ).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        ttk.Button(
            btn_frame2,
            text="📊 查看状态",
            style="Big.TButton",
            command=self.show_status
        ).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        log_frame = ttk.LabelFrame(main_frame, text="运行日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            font=("Consolas", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=10)

        ttk.Button(
            bottom_frame,
            text="安装依赖",
            command=self.install_deps
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            bottom_frame,
            text="使用帮助",
            command=self.show_help
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            bottom_frame,
            text="退出",
            command=self.on_closing
        ).pack(side=tk.RIGHT, padx=5)

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
                "环境警告",
                "需要 Python 3.9 或更高版本\n当前版本: " + sys.version.split()[0]
            )

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def toggle_scheduler(self):
        if self.scheduler_process and self.scheduler_process.poll() is None:
            self.scheduler_process.terminate()
            self.scheduler_btn.config(text="🖥️ 启动调度器")
            self.log("调度器已停止")
        else:
            self.start_scheduler()

    def start_scheduler(self):
        self.log("正在启动调度器...")

        venv_python = Path("venv/Scripts/python.exe")
        python_exe = str(venv_python) if venv_python.exists() else sys.executable

        try:
            self.scheduler_process = subprocess.Popen(
                [python_exe, "-m", "legacy.scheduler.simple_server"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            self.scheduler_btn.config(text="⏹️ 停止调度器")
            self.log("调度器已启动: http://localhost:8000")
            self.log("API 文档: http://localhost:8000/docs")

            threading.Thread(
                target=self._read_output,
                args=(self.scheduler_process,),
                daemon=True
            ).start()

        except Exception as e:
            self.log(f"启动失败: {e}")
            messagebox.showerror("错误", f"启动调度器失败:\n{e}")

    def _read_output(self, process):
        try:
            for line in iter(process.stdout.readline, ''):
                if line:
                    self.log(line.strip())
        except Exception as e:
            self.log(f"读取输出异常: {e}")

    def start_node(self):
        self.log("正在启动节点客户端...")

        venv_python = Path("venv/Scripts/python.exe")
        python_exe = str(venv_python) if venv_python.exists() else sys.executable

        try:
            self.node_process = subprocess.Popen(
                [python_exe, "-m", "legacy.node.simple_client"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            self.log("节点客户端已启动")

            threading.Thread(
                target=self._read_output,
                args=(self.node_process,),
                daemon=True
            ).start()

        except Exception as e:
            self.log(f"启动失败: {e}")
            messagebox.showerror("错误", f"启动节点失败:\n{e}")

    def open_web(self):
        try:
            webbrowser.open("http://localhost:8501")
            self.log("已打开 Web 界面")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开浏览器:\n{e}")

    def show_status(self):
        try:
            import requests
            response = requests.get("http://localhost:8000/stats", timeout=2)
            if response.status_code == 200:
                stats = response.json()
                msg = f"""系统状态

任务统计:
  总任务数: {stats.get('total_tasks', 0)}
  等待中: {stats.get('pending_tasks', 0)}
  运行中: {stats.get('running_tasks', 0)}
  已完成: {stats.get('completed_tasks', 0)}
  失败: {stats.get('failed_tasks', 0)}

节点统计:
  总节点数: {stats.get('total_nodes', 0)}
  可用节点: {stats.get('available_nodes', 0)}
"""
                messagebox.showinfo("系统状态", msg)
            else:
                messagebox.showwarning("警告", "调度器未响应")
        except Exception as e:
            messagebox.showwarning("警告", f"无法连接调度器\n请先启动调度器\n错误: {e}")

    def install_deps(self):
        self.log("正在安装依赖...")

        try:
            if not Path("venv").exists():
                subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
                self.log("虚拟环境创建成功")

            venv_python = Path("venv/Scripts/python.exe")
            python_exe = str(venv_python) if venv_python.exists() else sys.executable

            subprocess.run([python_exe, "-m", "pip", "install", "--upgrade", "pip"], check=True)
            subprocess.run([python_exe, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
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

2. 启动调度器:
   - 点击"启动调度器"
   - 等待启动完成
   - 访问 http://localhost:8000

3. 启动节点:
   - 确保调度器已运行
   - 点击"启动节点"
   - 节点将自动连接调度器

4. 提交任务:
   - 打开 Web 界面
   - 或使用命令行:
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

#!/usr/bin/env python3
"""
Idle-Sense 统一启动脚本
集成 Legacy 模块 + 网络发现 + 生产级可靠性

功能:
- 自动网络发现（组播 + DHT）
- 健康检查与故障转移
- 分布式锁（调度器选举）
- 任务重试与恢复
- 超时管理
- Prometheus 监控指标
- 事件总线

使用方法:
    python start.py
    python start.py --role scheduler
    python start.py --role worker --scheduler-url http://192.168.1.100:8000
"""

import argparse
import contextlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

SCHEDULER_PORT = 8000
FEDERATION_PORT = 8765


def print_banner():
    """打印启动横幅"""
    print("=" * 70)
    print("  Idle-Sense - 生产级分布式算力共享平台")
    print("  Production-Grade Distributed Computing Platform")
    print("=" * 70)
    print()


def check_dependencies():
    """检查依赖"""
    print("[检查] 正在检查依赖...")

    required_packages = [
        "fastapi", "uvicorn", "pydantic", "psutil"
    ]

    missing = []
    for pkg in required_packages:
        try:
            __import__(pkg)
            print(f"  ✓ {pkg}")
        except ImportError:
            missing.append(pkg)
            print(f"  ✗ {pkg} (缺失)")

    if missing:
        print(f"\n[警告] 缺少依赖包: {', '.join(missing)}")
        print("[提示] 请运行: pip install " + " ".join(missing))
        return False

    print("[检查] 所有依赖已满足\n")
    return True


def check_legacy_modules():
    """检查 Legacy 模块"""
    print("[检查] 正在检查 Legacy 模块...")

    modules = [
        ("health_check", "健康检查"),
        ("distributed_lock", "分布式锁"),
        ("retry_recovery", "重试恢复"),
        ("timeout_manager", "超时管理"),
        ("monitoring", "监控指标"),
        ("event_bus", "事件总线"),
    ]

    available = []
    for module_name, display_name in modules:
        try:
            __import__(f"legacy.{module_name}")
            print(f"  ✓ {display_name}")
            available.append(module_name)
        except ImportError:
            print(f"  ✗ {display_name} (不可用)")

    print(f"\n[检查] 可用模块: {len(available)}/{len(modules)}\n")
    return available


def start_scheduler(port: int = SCHEDULER_PORT):
    """启动调度器"""
    print(f"[启动] 正在启动调度器 (端口: {port})...")

    env = os.environ.copy()
    env["PORT"] = str(port)
    env["ENABLE_FEDERATION"] = "true"
    env["FEDERATION_PORT"] = str(FEDERATION_PORT)
    env["LEGACY_INTEGRATION"] = "true"
    env["STORAGE_BACKEND"] = "sqlite"

    process = subprocess.Popen(
        [sys.executable, "-m", "legacy.scheduler.simple_server"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    print(f"[启动] 调度器已启动 (PID: {process.pid})")
    return process


def start_worker(scheduler_url: str):
    """启动工作节点"""
    print(f"[启动] 正在启动工作节点 (连接: {scheduler_url})...")

    env = os.environ.copy()
    env["SCHEDULER_URL"] = scheduler_url
    env["LEGACY_INTEGRATION"] = "true"

    process = subprocess.Popen(
        [sys.executable, "-m", "legacy.node.simple_client", "--scheduler-url", scheduler_url],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    print(f"[启动] 工作节点已启动 (PID: {process.pid})")
    return process


def start_web_ui():
    """启动 Web 界面"""
    print("[启动] 正在启动 Web 界面...")

    process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "src/presentation/streamlit/app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    print(f"[启动] Web 界面已启动 (PID: {process.pid})")
    return process


def log_output(process, name: str):
    """记录进程输出"""
    try:
        for line in iter(process.stdout.readline, ""):
            if line:
                print(f"[{name}] {line.strip()}")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Idle-Sense 统一启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python start.py                    # 自动模式（推荐）
  python start.py --role scheduler   # 仅启动调度器
  python start.py --role worker      # 仅启动工作节点
  python start.py --no-web           # 不启动 Web 界面
        """
    )

    parser.add_argument(
        "--role",
        choices=["auto", "scheduler", "worker"],
        default="auto",
        help="节点角色: auto(自动), scheduler(调度器), worker(工作节点)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=SCHEDULER_PORT,
        help=f"调度器端口 (默认: {SCHEDULER_PORT})"
    )

    parser.add_argument(
        "--scheduler-url",
        type=str,
        default=None,
        help="调度器 URL (工作节点模式)"
    )

    parser.add_argument(
        "--no-web",
        action="store_true",
        help="不启动 Web 界面"
    )

    args = parser.parse_args()

    print_banner()

    if not check_dependencies():
        sys.exit(1)

    check_legacy_modules()

    processes = []

    def signal_handler(sig, frame):
        print("\n[系统] 正在停止所有服务...")
        for p, name in processes:
            try:
                p.terminate()
                p.wait(timeout=5)
                print(f"[停止] {name} 已停止")
            except Exception:
                with contextlib.suppress(Exception):
                    p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    import threading

    if args.role == "scheduler":
        p = start_scheduler(args.port)
        processes.append((p, "调度器"))
        threading.Thread(target=log_output, args=(p, "调度器"), daemon=True).start()

    elif args.role == "worker":
        if not args.scheduler_url:
            print("[错误] 工作节点模式需要指定 --scheduler-url")
            sys.exit(1)
        p = start_worker(args.scheduler_url)
        processes.append((p, "工作节点"))
        threading.Thread(target=log_output, args=(p, "工作节点"), daemon=True).start()

    else:
        p = start_scheduler(args.port)
        processes.append((p, "调度器"))
        threading.Thread(target=log_output, args=(p, "调度器"), daemon=True).start()

        time.sleep(3)

        scheduler_url = f"http://localhost:{args.port}"
        p = start_worker(scheduler_url)
        processes.append((p, "工作节点"))
        threading.Thread(target=log_output, args=(p, "工作节点"), daemon=True).start()

    if not args.no_web:
        time.sleep(2)
        p = start_web_ui()
        processes.append((p, "Web界面"))
        threading.Thread(target=log_output, args=(p, "Web界面"), daemon=True).start()

    print()
    print("=" * 70)
    print("  服务已启动!")
    print("=" * 70)
    print()
    print("访问地址:")
    print("  - Web 界面: http://localhost:8501")
    print(f"  - API 文档: http://localhost:{args.port}/docs")
    print(f"  - 健康检查: http://localhost:{args.port}/health")
    print()
    print("Legacy 模块端点:")
    print(f"  - 详细健康检查: http://localhost:{args.port}/api/health/detailed")
    print(f"  - Prometheus 指标: http://localhost:{args.port}/metrics")
    print(f"  - 模块状态: http://localhost:{args.port}/api/legacy/status")
    print()
    print("按 Ctrl+C 停止服务")
    print("=" * 70)

    try:
        while True:
            time.sleep(1)
            dead_processes = [(p, n) for p, n in processes if p.poll() is not None]
            for p, n in dead_processes:
                print(f"[警告] {n} 进程已退出 (返回码: {p.returncode})")
                processes.remove((p, n))

            if not processes:
                print("[错误] 所有进程已退出")
                break
    except KeyboardInterrupt:
        pass
    finally:
        signal_handler(None, None)


if __name__ == "__main__":
    main()

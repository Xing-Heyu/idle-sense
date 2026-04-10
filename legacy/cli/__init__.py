"""
CLI Command Line Interface for Idle-Accelerator.

Usage:
    idle-accelerator scheduler start
    idle-accelerator node start --scheduler-url http://localhost:8000
    idle-accelerator task submit --code "print('hello')"
    idle-accelerator status
    idle-accelerator version
"""

import argparse
import json
import sys
import time


def create_parser() -> argparse.ArgumentParser:
    """Create the main CLI parser."""
    parser = argparse.ArgumentParser(
        prog="idle-accelerator",
        description="Distributed computing platform utilizing idle computer resources",
    )

    parser.add_argument("--version", "-v", action="store_true", help="Show version information")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    _add_scheduler_parser(subparsers)
    _add_node_parser(subparsers)
    _add_task_parser(subparsers)
    _add_status_parser(subparsers)

    return parser


def _add_scheduler_parser(subparsers):
    """Add scheduler subcommand parser."""
    scheduler_parser = subparsers.add_parser("scheduler", help="Scheduler management commands")

    scheduler_subparsers = scheduler_parser.add_subparsers(dest="scheduler_command")

    start_parser = scheduler_subparsers.add_parser("start", help="Start the scheduler")
    start_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    start_parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    start_parser.add_argument(
        "--storage", choices=["memory", "redis", "sqlite"], default="memory", help="Storage backend"
    )
    start_parser.add_argument(
        "--redis-url", default="redis://localhost:6379/0", help="Redis URL (if storage=redis)"
    )
    start_parser.add_argument(
        "--sqlite-path", default="data/scheduler.db", help="SQLite path (if storage=sqlite)"
    )

    scheduler_subparsers.add_parser("status", help="Check scheduler status")


def _add_node_parser(subparsers):
    """Add node subcommand parser."""
    node_parser = subparsers.add_parser("node", help="Node management commands")

    node_subparsers = node_parser.add_subparsers(dest="node_command")

    start_parser = node_subparsers.add_parser("start", help="Start a node client")
    start_parser.add_argument(
        "--scheduler-url", default="http://localhost:8000", help="Scheduler URL"
    )
    start_parser.add_argument("--node-id", help="Node ID (auto-generated if not provided)")
    start_parser.add_argument(
        "--idle-threshold", type=int, default=300, help="Idle threshold in seconds"
    )
    start_parser.add_argument(
        "--cpu-threshold", type=float, default=30.0, help="CPU usage threshold"
    )
    start_parser.add_argument(
        "--memory-threshold", type=float, default=70.0, help="Memory usage threshold"
    )

    node_subparsers.add_parser("list", help="List all nodes")
    node_subparsers.add_parser("status", help="Show node status")


def _add_task_parser(subparsers):
    """Add task subcommand parser."""
    task_parser = subparsers.add_parser("task", help="Task management commands")

    task_subparsers = task_parser.add_subparsers(dest="task_command")

    submit_parser = task_subparsers.add_parser("submit", help="Submit a task")
    submit_parser.add_argument("--code", "-c", help="Python code to execute")
    submit_parser.add_argument("--file", "-f", help="File containing Python code")
    submit_parser.add_argument("--timeout", type=int, default=300, help="Execution timeout")
    submit_parser.add_argument("--cpu", type=float, default=1.0, help="CPU requirement")
    submit_parser.add_argument("--memory", type=int, default=512, help="Memory requirement in MB")
    submit_parser.add_argument(
        "--scheduler-url", default="http://localhost:8000", help="Scheduler URL"
    )

    list_parser = task_subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument(
        "--status", choices=["pending", "running", "completed", "failed"], help="Filter by status"
    )
    list_parser.add_argument("--limit", type=int, default=20, help="Maximum tasks to show")
    list_parser.add_argument(
        "--scheduler-url", default="http://localhost:8000", help="Scheduler URL"
    )

    status_parser = task_subparsers.add_parser("status", help="Get task status")
    status_parser.add_argument("task_id", type=int, help="Task ID")
    status_parser.add_argument(
        "--scheduler-url", default="http://localhost:8000", help="Scheduler URL"
    )

    result_parser = task_subparsers.add_parser("result", help="Get task result")
    result_parser.add_argument("task_id", type=int, help="Task ID")
    result_parser.add_argument(
        "--scheduler-url", default="http://localhost:8000", help="Scheduler URL"
    )


def _add_status_parser(subparsers):
    """Add status subcommand parser."""
    status_parser = subparsers.add_parser("status", help="Show system status")
    status_parser.add_argument(
        "--scheduler-url", default="http://localhost:8000", help="Scheduler URL"
    )
    status_parser.add_argument("--json", action="store_true", help="Output as JSON")


def cmd_scheduler_start(args):
    """Start the scheduler."""
    print(f"Starting scheduler on {args.host}:{args.port}")
    print(f"Storage backend: {args.storage}")

    try:
        if args.storage == "redis":
            print(f"Redis URL: {args.redis_url}")
        elif args.storage == "sqlite":
            print(f"SQLite path: {args.sqlite_path}")

        import uvicorn
        from scheduler.simple_server import app

        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    except ImportError as e:
        print(f"Error: {e}")
        print("Please install required dependencies: pip install -e '.[scheduler]'")
        sys.exit(1)


def cmd_node_start(args):
    """Start a node client."""
    print(f"Starting node client, connecting to {args.scheduler_url}")

    try:
        from node.simple_client import NodeClient

        client = NodeClient(
            scheduler_url=args.scheduler_url,
            node_id=args.node_id,
            idle_threshold=args.idle_threshold,
            cpu_threshold=args.cpu_threshold,
            memory_threshold=args.memory_threshold,
        )

        print(f"Node ID: {client.node_id}")
        print("Press Ctrl+C to stop")

        client.run()
    except ImportError as e:
        print(f"Error: {e}")
        print("Please install required dependencies: pip install -e '.[node]'")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nNode stopped")


def cmd_task_submit(args):
    """Submit a task."""
    if args.code:
        code = args.code
    elif args.file:
        with open(args.file) as f:
            code = f.read()
    else:
        print("Error: Either --code or --file must be provided")
        sys.exit(1)

    try:
        import requests

        response = requests.post(
            f"{args.scheduler_url}/submit",
            json={
                "code": code,
                "timeout": args.timeout,
                "resources": {"cpu": args.cpu, "memory": args.memory},
            },
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            print("Task submitted successfully!")
            print(f"Task ID: {result.get('task_id')}")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            sys.exit(1)
    except ImportError:
        print("Error: requests module not installed")
        print("Please install: pip install requests")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_task_list(args):
    """List tasks."""
    try:
        import requests

        params = {"limit": args.limit}
        if args.status:
            params["status"] = args.status

        response = requests.get(f"{args.scheduler_url}/tasks", params=params, timeout=10)

        if response.status_code == 200:
            tasks = response.json()

            if not tasks:
                print("No tasks found")
                return

            print(f"{'ID':<8} {'Status':<12} {'Created':<20} {'Node':<15}")
            print("-" * 60)

            for task in tasks:
                created = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(task.get("created_at", 0))
                )
                node = task.get("assigned_node", "-") or "-"
                print(f"{task['task_id']:<8} {task['status']:<12} {created:<20} {node:<15}")
        else:
            print(f"Error: {response.status_code}")
            sys.exit(1)
    except ImportError:
        print("Error: requests module not installed")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_task_status(args):
    """Get task status."""
    try:
        import requests

        response = requests.get(f"{args.scheduler_url}/status/{args.task_id}", timeout=10)

        if response.status_code == 200:
            task = response.json()

            print(f"Task ID: {task['task_id']}")
            print(f"Status: {task['status']}")
            print(
                f"Created: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(task.get('created_at', 0)))}"
            )

            if task.get("assigned_node"):
                print(f"Assigned Node: {task['assigned_node']}")

            if task.get("result"):
                print(f"Result: {task['result'][:200]}...")

            if task.get("error"):
                print(f"Error: {task['error']}")
        else:
            print(f"Error: {response.status_code}")
            sys.exit(1)
    except ImportError:
        print("Error: requests module not installed")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_scheduler_status(args):
    """Check scheduler status."""
    try:
        import requests

        response = requests.get("http://localhost:8000/health", timeout=5)

        if response.status_code == 200:
            print("Scheduler Status: Running")
            print("URL: http://localhost:8000")

            stats_response = requests.get("http://localhost:8000/stats", timeout=5)

            if stats_response.status_code == 200:
                stats = stats_response.json()
                print("\nStatistics:")
                print(f"  Total Tasks: {stats.get('total_tasks', 0)}")
                print(f"  Pending Tasks: {stats.get('pending_tasks', 0)}")
                print(f"  Running Tasks: {stats.get('running_tasks', 0)}")
                print(f"  Completed Tasks: {stats.get('completed_tasks', 0)}")
                print(f"  Failed Tasks: {stats.get('failed_tasks', 0)}")
                print(f"  Total Nodes: {stats.get('total_nodes', 0)}")
                print(f"  Available Nodes: {stats.get('available_nodes', 0)}")
        else:
            print(f"Scheduler Status: Error (HTTP {response.status_code})")
            sys.exit(1)
    except ImportError:
        print("Error: requests module not installed")
        print("Please install: pip install requests")
        sys.exit(1)
    except Exception as e:
        print("Scheduler Status: Not Running")
        print(f"Error: {e}")
        sys.exit(1)


def cmd_node_list(args):
    """List all nodes."""
    try:
        import requests

        response = requests.get("http://localhost:8000/api/nodes", timeout=10)

        if response.status_code == 200:
            nodes = response.json()

            if not nodes:
                print("No nodes registered")
                return

            print(
                f"{'Node ID':<20} {'Status':<12} {'CPU':<8} {'Memory':<10} {'Last Heartbeat':<20}"
            )
            print("-" * 80)

            for node in nodes:
                node_id = node.get("node_id", "-")[:18]
                status = node.get("status", "unknown")
                cpu = f"{node.get('capacity', {}).get('cpu', 0):.1f}"
                memory = f"{node.get('capacity', {}).get('memory', 0)} MB"
                last_heartbeat = node.get("last_heartbeat", 0)

                if last_heartbeat:
                    heartbeat_str = time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(last_heartbeat)
                    )
                else:
                    heartbeat_str = "-"

                print(f"{node_id:<20} {status:<12} {cpu:<8} {memory:<10} {heartbeat_str:<20}")
        else:
            print(f"Error: {response.status_code}")
            sys.exit(1)
    except ImportError:
        print("Error: requests module not installed")
        print("Please install: pip install requests")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        print("Is the scheduler running?")
        sys.exit(1)


def cmd_status(args):
    """Show system status."""
    try:
        import requests

        response = requests.get(f"{args.scheduler_url}/stats", timeout=10)

        if response.status_code == 200:
            stats = response.json()

            if args.json:
                print(json.dumps(stats, indent=2))
            else:
                print("=== System Status ===")
                print("\nTasks:")
                print(f"  Total: {stats.get('total_tasks', 0)}")
                print(f"  Pending: {stats.get('pending_tasks', 0)}")
                print(f"  Running: {stats.get('running_tasks', 0)}")
                print(f"  Completed: {stats.get('completed_tasks', 0)}")
                print(f"  Failed: {stats.get('failed_tasks', 0)}")

                print("\nNodes:")
                print(f"  Total: {stats.get('total_nodes', 0)}")
                print(f"  Available: {stats.get('available_nodes', 0)}")
                print(f"  Busy: {stats.get('busy_nodes', 0)}")
                print(f"  Offline: {stats.get('offline_nodes', 0)}")
        else:
            print(f"Error: {response.status_code}")
            print("Is the scheduler running?")
            sys.exit(1)
    except ImportError:
        print("Error: requests module not installed")
        sys.exit(1)
    except Exception as e:
        print(f"Error connecting to scheduler: {e}")
        print("Is the scheduler running?")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.version:
        print("idle-accelerator version 1.0.0")
        return

    if not args.command:
        parser.print_help()
        return

    if args.command == "scheduler":
        if args.scheduler_command == "start":
            cmd_scheduler_start(args)
        elif args.scheduler_command == "status":
            cmd_scheduler_status(args)
        else:
            parser.print_help()

    elif args.command == "node":
        if args.node_command == "start":
            cmd_node_start(args)
        elif args.node_command == "list":
            cmd_node_list(args)
        else:
            parser.print_help()

    elif args.command == "task":
        if args.task_command == "submit":
            cmd_task_submit(args)
        elif args.task_command == "list":
            cmd_task_list(args)
        elif args.task_command == "status":
            cmd_task_status(args)
        else:
            parser.print_help()

    elif args.command == "status":
        cmd_status(args)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

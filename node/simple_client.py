"""
node/simple_client.py
Minimal Node Client - Final Verified Version
"""

import requests
import time
import sys
import os
import traceback
import signal
from typing import Optional, Dict, Any
from pathlib import Path

# 📝 修复：更可靠的路径处理
def setup_paths() -> None:
    """Setup Python paths for imports"""
    # 获取项目根目录
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    
    # 添加项目根目录到路径（如果不在sys.path中）
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # 添加当前目录
    current_dir = str(current_file.parent)
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

setup_paths()

# 📝 修复：尝试导入idle_sense，但有降级处理
try:
    from idle_sense import is_idle, get_system_status
    IDLE_SENSE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: idle_sense not available: {e}")
    print("Will use simplified idle detection")
    IDLE_SENSE_AVAILABLE = False

# 配置
SERVER_URL = "http://localhost:8000"
CHECK_INTERVAL = 30  # 秒
TASK_TIMEOUT = 300   # 任务执行超时时间（秒）
MAX_RETRIES = 3      # 最大重试次数

class TimeoutException(Exception):
    """Custom exception for timeout"""
    pass

def timeout_handler(signum, frame):
    """Signal handler for timeout"""
    raise TimeoutException("Task execution timeout")

def safe_execute(code: str, timeout: int = TASK_TIMEOUT) -> str:
    """
    Safely execute Python code with timeout and restricted environment
    """
    # 📝 修复：创建高度受限的执行环境
    restricted_builtins = {
        # 基本函数
        'print': print,
        'len': len, 'range': range, 'sum': sum,
        'abs': abs, 'round': round, 'min': min, 'max': max,
        'sorted': sorted, 'reversed': reversed,
        'enumerate': enumerate, 'zip': zip,
        
        # 类型转换
        'str': str, 'int': int, 'float': float,
        'bool': bool, 'list': list, 'dict': dict, 'tuple': tuple,
        'set': set, 'frozenset': frozenset,
        
        # 数学函数（安全的）
        'pow': pow, 'divmod': divmod,
    }
    
    # 进一步限制的全局变量
    safe_globals = {
        '__builtins__': restricted_builtins,
        '__name__': '__main__',
        '__result__': None,
    }
    
    # 设置超时处理（仅Unix系统）
    original_handler = None
    if hasattr(signal, 'SIGALRM'):
        original_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
    
    try:
        # 尝试编译代码（语法检查）
        try:
            compiled_code = compile(code, '<task>', 'exec')
        except SyntaxError as e:
            return f"Syntax Error: {e}"
        
        # 执行代码
        exec(compiled_code, safe_globals)
        
        # 获取结果
        result = safe_globals.get('__result__', 'Execution completed successfully')
        return f"Success: {result}"
        
    except TimeoutException:
        return "Error: Task execution timeout"
    except MemoryError:
        return "Error: Memory limit exceeded"
    except Exception as e:
        # 📝 修复：限制错误信息长度
        error_msg = str(e)
        if len(error_msg) > 200:
            error_msg = error_msg[:197] + "..."
        return f"Error: {error_msg}"
    
    finally:
        # 恢复信号处理
        if hasattr(signal, 'SIGALRM') and original_handler:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, original_handler)

def check_idle() -> bool:
    """Check if system is idle"""
    if IDLE_SENSE_AVAILABLE:
        try:
            # 📝 修复：实际使用idle_sense库
            return is_idle(idle_threshold_sec=60)  # 1分钟无活动
        except Exception as e:
            print(f"Warning: idle_sense.is_idle() failed: {e}")
            # 降级到简单检测
            return True
    else:
        # 简化版本：总是返回True（用于测试）
        print("Note: Using simplified idle detection (always True)")
        return True

def get_system_info() -> Dict[str, Any]:
    """Get system information for logging"""
    if IDLE_SENSE_AVAILABLE:
        try:
            status = get_system_status()
            return {
                'idle': status.get('is_user_idle', False),
                'cpu_percent': status.get('cpu_percent', 0),
                'memory_percent': status.get('memory_percent', 0),
                'platform': status.get('platform', 'unknown'),
            }
        except Exception:
            pass
    
    return {
        'idle': True,
        'cpu_percent': 0,
        'memory_percent': 0,
        'platform': sys.platform,
    }

def make_request(method: str, url: str, **kwargs) -> Optional[Dict[str, Any]]:
    """Make HTTP request with retry logic"""
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.request(method, url, timeout=10, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt == MAX_RETRIES - 1:
                print(f"Request failed after {MAX_RETRIES} attempts: {e}")
                return None
            print(f"Request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            time.sleep(2 ** attempt)  # 指数退避
    
    return None

def main():
    """Main client loop"""
    print("=" * 60)
    print("Idle Computing Node Client")
    print("=" * 60)
    
    # 显示系统信息
    info = get_system_info()
    print(f"Platform: {info['platform']}")
    print(f"Idle sense: {'Available' if IDLE_SENSE_AVAILABLE else 'Not available'}")
    print(f"Scheduler: {SERVER_URL}")
    print(f"Check interval: {CHECK_INTERVAL}s")
    print("-" * 60)
    
    task_count = 0
    error_count = 0
    
    try:
        while True:
            try:
                # 显示心跳
                current_time = time.strftime('%H:%M:%S')
                
                # 检查是否闲置
                if check_idle():
                    # 获取任务
                    task_data = make_request("GET", f"{SERVER_URL}/get_task")
                    
                    if task_data and task_data.get("task_id") and task_data.get("code"):
                        task_id = task_data["task_id"]
                        code = task_data["code"]
                        
                        task_count += 1
                        print(f"[{current_time}] Task #{task_id} received (Total: {task_count})")
                        
                        # 执行任务
                        start_time = time.time()
                        result = safe_execute(code)
                        execution_time = time.time() - start_time
                        
                        # 提交结果
                        submit_data = make_request(
                            "POST", 
                            f"{SERVER_URL}/submit_result",
                            json={"task_id": task_id, "result": result}
                        )
                        
                        if submit_data:
                            print(f"  ✓ Completed in {execution_time:.1f}s")
                            print(f"  Result: {result[:80]}{'...' if len(result) > 80 else ''}")
                        else:
                            error_count += 1
                            print(f"  ✗ Failed to submit result")
                    else:
                        if task_data and task_data.get("status") == "no_tasks":
                            print(f"[{current_time}] No tasks available")
                        else:
                            print(f"[{current_time}] No response from scheduler")
                else:
                    # 系统不空闲
                    print(f"[{current_time}] System not idle (CPU: {info['cpu_percent']}%, "
                          f"Memory: {info['memory_percent']}%)")
                
                # 等待下一个检查周期
                print("-" * 40)
                time.sleep(CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                print("\n" + "=" * 60)
                print("Client stopped by user")
                break
            except Exception as e:
                error_count += 1
                print(f"[{time.strftime('%H:%M:%S')}] Unexpected error: {e}")
                traceback.print_exc()
                time.sleep(min(60, CHECK_INTERVAL * 2))  # 错误时等待更久
    
    finally:
        # 总结报告
        print("\n" + "=" * 60)
        print("Client Summary:")
        print(f"  Tasks executed: {task_count}")
        print(f"  Errors encountered: {error_count}")
        print(f"  Idle sense: {'Available' if IDLE_SENSE_AVAILABLE else 'Not available'}")
        print("=" * 60)

if __name__ == "__main__":
    main()
    

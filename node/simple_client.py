"""
node/simple_client.py
极简节点客户端 - 最终验证版
"""

import requests
import time
import sys
import os
import traceback

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置
SERVER_URL = "http://localhost:8000"
CHECK_INTERVAL = 30  # 秒

def safe_execute(code: str) -> str:
    """安全执行Python代码"""
    try:
        # 创建安全的全局变量
        safe_globals = {}
        safe_globals['__builtins__'] = {
            'print': print,
            'len': len, 'range': range, 'sum': sum,
            'str': str, 'int': int, 'float': float,
            'list': list, 'dict': dict, 'tuple': tuple,
            'bool': bool, 'type': type, 'min': min, 'max': max,
            'abs': abs, 'round': round, 'sorted': sorted,
            'enumerate': enumerate, 'zip': zip
        }
        
        # 安全执行
        exec(code, safe_globals)
        
        # 如果有__result__变量，返回它
        result = safe_globals.get('__result__', '执行成功')
        return f"成功: {result}"
        
    except Exception as e:
        return f"错误: {str(e)}"

def check_idle() -> bool:
    """检查是否闲置（简化版，总返回True用于测试）"""
    # 实际项目中这里会调用idle-sense
    return True

def main():
    print("节点客户端启动")
    print(f"调度中心: {SERVER_URL}")
    print("按 Ctrl+C 停止\n")
    
    while True:
        try:
            # 检查是否闲置
            if check_idle():
                # 请求任务
                response = requests.get(f"{SERVER_URL}/get_task", timeout=10)
                data = response.json()
                
                if data.get("task_id") and data.get("code"):
                    task_id = data["task_id"]
                    code = data["code"]
                    
                    print(f"[{time.strftime('%H:%M:%S')}] 执行任务 #{task_id}")
                    
                    # 执行任务
                    result = safe_execute(code)
                    
                    # 提交结果
                    requests.post(
                        f"{SERVER_URL}/submit_result",
                        params={"task_id": task_id, "result": result}
                    )
                    
                    print(f"  结果: {result[:100]}")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] 无任务")
            
            # 等待
            time.sleep(CHECK_INTERVAL)
            
        except requests.exceptions.ConnectionError:
            print(f"[{time.strftime('%H:%M:%S')}] 无法连接服务器，10秒后重试")
            time.sleep(10)
        except KeyboardInterrupt:
            print("\n客户端停止")
            break
        except Exception as e:
            print(f"未知错误: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()

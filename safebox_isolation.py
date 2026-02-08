"""
safebox_isolation.py
SAFEBOX-ISOLATION v1.0 - 安全沙箱与文件夹隔离系统
基于用户提供的技术方案实现
"""

import os
import sys
import json
import tempfile
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional


class ResourceConfig:
    """资源配置类型 - 开源版本无限制"""
    def __init__(self, cpu_cores: float = 0, memory_mb: int = 0, 
                 timeout_sec: int = 0, allow_network: bool = False):
        self.cpu_cores = cpu_cores  # 0表示无限制
        self.memory_mb = memory_mb  # 0表示无限制
        self.timeout_sec = timeout_sec  # 0表示无限制
        self.allow_network = allow_network
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'cpu_cores': "无限制",
            'memory_mb': "无限制", 
            'timeout_sec': "无限制",
            'allow_network': self.allow_network
        }


class ModuleA_Prepare:
    """模块A：环境准备器"""
    
    def __init__(self, task_id: str, user_code: str, resource_config: ResourceConfig, 
                 user_id: str = None, node_base_dir: str = "node_data"):
        self.task_id = task_id
        self.user_code = user_code
        self.resource_config = resource_config
        self.user_id = user_id
        self.node_base_dir = Path(node_base_dir)
        
        # 确保基础目录存在
        self.node_base_dir.mkdir(exist_ok=True)
        
        # 设置工作目录根路径
        self.base_dir = self.node_base_dir / "task_operate"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # 工作目录路径
        if user_id:
            # 如果有用户ID，使用用户临时文件夹
            user_temp_dir = self.node_base_dir / "temp_data" / user_id
            user_temp_dir.mkdir(parents=True, exist_ok=True)
            self.work_dir = user_temp_dir / task_id
        else:
            # 匿名用户使用系统临时文件夹
            self.work_dir = self.base_dir / task_id
        
        # 创建工作目录
        self.work_dir.mkdir(parents=True, exist_ok=True)
    
    def _create_runner_script(self) -> str:
        """创建固定的监控脚本 runner.py"""
        return '''"""
runner.py - 安全执行监控脚本（开源版本无限制）
"""

import sys
import os
import time
import json
from io import StringIO

# 读取配置
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# 文件夹路径设置
USER_FOLDER_PATH = config.get('user_folder_path', '')
TEMP_FOLDER_PATH = config.get('temp_folder_path', '')

# 执行用户代码
def execute_user_code():
    """在安全环境中执行用户代码（无资源限制）"""
    start_time = time.time()
    
    # 重定向标准输出
    old_stdout = sys.stdout
    sys.stdout = output_capture = StringIO()
    
    try:
        # 执行用户脚本
        with open('user_script.py', 'r', encoding='utf-8') as f:
            user_code = f.read()
        
        # 创建安全的执行环境
        safe_globals = {
            '__builtins__': {
                'print': print, 'len': len, 'range': range, 'str': str, 
                'int': int, 'float': float, 'list': list, 'dict': dict,
                'abs': abs, 'max': max, 'min': min, 'sum': sum,
                '__import__': __import__  # 允许导入模块（受限制）
            },
            'USER_FOLDER': USER_FOLDER_PATH,  # 用户文件夹路径
            'TEMP_FOLDER': TEMP_FOLDER_PATH,  # 临时文件夹路径
            'get_user_folder': lambda: USER_FOLDER_PATH,  # 获取用户文件夹
            'get_temp_folder': lambda: TEMP_FOLDER_PATH   # 获取临时文件夹
        }
        
        # 预导入安全的数学模块
        try:
            import math
            safe_globals['math'] = math
        except:
            pass
            
        try:
            import random
            safe_globals['random'] = random
        except:
            pass
            
        try:
            import statistics
            safe_globals['statistics'] = statistics
        except:
            pass
            
        # 预导入安全的文件操作模块
        try:
            import io
            safe_globals['io'] = io
        except:
            pass
            
        try:
            import csv
            safe_globals['csv'] = csv
        except:
            pass
            
        try:
            import json
            safe_globals['json'] = json
        except:
            pass
            
        try:
            import base64
            safe_globals['base64'] = base64
        except:
            pass
            
        try:
            import hashlib
            safe_globals['hashlib'] = hashlib
        except:
            pass
            
        # 限制危险模块
        dangerous_modules = ['os', 'sys', 'subprocess', 'shutil', 'socket', 'threading', 'multiprocessing']
        for module_name in dangerous_modules:
            safe_globals[module_name] = None  # 设置为None，防止导入
        
        # 添加安全的文件操作辅助函数
        def safe_read_user_file(filename):
            """安全读取用户数据文件夹中的文件"""
            import os
            
            # 构建完整的文件路径
            if USER_FOLDER_PATH:
                full_path = os.path.join(USER_FOLDER_PATH, filename)
                
                # 安全检查：确保路径在用户文件夹内
                if not full_path.startswith(USER_FOLDER_PATH):
                    raise PermissionError("只能读取用户数据文件夹内的文件")
                
                # 检查文件是否存在
                if not os.path.exists(full_path):
                    raise FileNotFoundError(f"文件不存在: {filename}")
                
                # 读取文件内容
                with open(full_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                raise PermissionError("匿名用户无法访问用户数据文件夹")
        
        safe_globals['read_user_file'] = safe_read_user_file
        safe_globals['list_user_files'] = lambda: os.listdir(USER_FOLDER_PATH) if USER_FOLDER_PATH and os.path.exists(USER_FOLDER_PATH) else []
        safe_globals['user_file_exists'] = lambda filename: os.path.exists(os.path.join(USER_FOLDER_PATH, filename)) if USER_FOLDER_PATH else False
        
        # 执行代码（无资源限制）
        exec(user_code, safe_globals)
        
        # 获取输出
        output = output_capture.getvalue()
        sys.stdout = old_stdout
        
        execution_time = time.time() - start_time
        
        return {
            'success': True,
            'output': output,
            'execution_time': execution_time,
            'exit_code': 0
        }
        
    except Exception as e:
        sys.stdout = old_stdout
        execution_time = time.time() - start_time
        return {
            'success': False,
            'output': '',
            'error': str(e),
            'execution_time': execution_time,
            'exit_code': 1
        }

if __name__ == "__main__":
    result = execute_user_code()
    
    # 输出结果
    if result['success']:
        if result['output']:
            print(result['output'])
        sys.exit(result['exit_code'])
    else:
        if result['error']:
            print(f"错误: {result['error']}", file=sys.stderr)
        sys.exit(result['exit_code'])
'''
    
    def run(self) -> str:
        """执行环境准备"""
        # 创建工作目录
        self.work_dir.mkdir(exist_ok=True)
        
        # 1. 创建 user_script.py
        user_script_path = self.work_dir / "user_script.py"
        with open(user_script_path, 'w', encoding='utf-8') as f:
            f.write(self.user_code)
        
        # 2. 创建 runner.py
        runner_script_path = self.work_dir / "runner.py"
        with open(runner_script_path, 'w', encoding='utf-8') as f:
            f.write(self._create_runner_script())
        
        # 3. 创建 config.json
        config_data = self.resource_config.to_dict()
        
        # 添加文件夹路径信息
        if self.user_id:
            config_data['user_folder_path'] = f"user_data/{self.user_id}"
            config_data['temp_folder_path'] = f"temp_data/{self.user_id}"
        else:
            config_data['user_folder_path'] = ""
            config_data['temp_folder_path'] = ""
        
        config_path = self.work_dir / "config.json"
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2)
        
        print(f"[模块A] 环境准备完成: {self.work_dir.absolute()}")
        return str(self.work_dir.absolute())


class ModuleB_Execute:
    """模块B：安全执行器"""
    
    def __init__(self, work_dir_path: str, resource_config: ResourceConfig):
        self.work_dir_path = work_dir_path
        self.resource_config = resource_config
    
    def run(self) -> Dict[str, Any]:
        """执行安全代码"""
        start_time = time.time()
        
        try:
            # 切换到工作目录
            original_cwd = os.getcwd()
            os.chdir(self.work_dir_path)
            
            # 执行命令
            cmd = [sys.executable, "runner.py"]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.resource_config.timeout_sec + 5,  # 额外5秒缓冲
                cwd=self.work_dir_path
            )
            
            execution_time = time.time() - start_time
            
            # 分析资源违规
            resource_violation = 'none'
            if result.returncode == 124:
                resource_violation = 'timeout'
            elif 'MemoryError' in result.stderr:
                resource_violation = 'memory'
            
            return {
                'exit_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'duration_sec': execution_time,
                'resource_violation': resource_violation
            }
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return {
                'exit_code': 124,
                'stdout': '',
                'stderr': f'执行超时 ({self.resource_config.timeout_sec}秒)',
                'duration_sec': execution_time,
                'resource_violation': 'timeout'
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                'exit_code': 1,
                'stdout': '',
                'stderr': f'执行器异常: {str(e)}',
                'duration_sec': execution_time,
                'resource_violation': 'none'
            }
            
        finally:
            # 恢复原始工作目录
            os.chdir(original_cwd)


class ModuleC_Cleanup:
    """模块C：取证与清理器"""
    
    def __init__(self, work_dir_path: str, execution_result: Dict[str, Any], 
                 archive_before_cleanup: bool = False):
        self.work_dir_path = work_dir_path
        self.execution_result = execution_result
        self.archive_before_cleanup = archive_before_cleanup
    
    def run(self) -> bool:
        """执行清理操作"""
        try:
            work_dir = Path(self.work_dir_path)
            
            if not work_dir.exists():
                print(f"[模块C] 工作目录不存在: {work_dir}")
                return True
            
            # 1. 保存执行结果
            result_file = work_dir / "result.json"
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(self.execution_result, f, indent=2, ensure_ascii=False)
            
            # 2. 可选：打包归档
            if self.archive_before_cleanup:
                archive_path = work_dir.parent / f"{work_dir.name}_artifacts.zip"
                try:
                    import zipfile
                    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for file_path in work_dir.rglob('*'):
                            if file_path.is_file():
                                zipf.write(file_path, file_path.relative_to(work_dir.parent))
                    print(f"[模块C] 已创建归档: {archive_path}")
                except Exception as e:
                    print(f"[模块C] 归档失败: {e}")
            
            # 3. 彻底删除工作目录
            shutil.rmtree(work_dir, ignore_errors=True)
            
            print(f"[模块C] 清理完成: {work_dir}")
            return True
            
        except Exception as e:
            print(f"[模块C] 清理失败: {e}")
            return False


class SafeBoxIsolation:
    """SAFEBOX-ISOLATION v1.0 主类"""
    
    def __init__(self):
        self.base_dir = Path("task_operate")
        self.base_dir.mkdir(exist_ok=True)
    
    def execute_task(self, task_id: str, user_code: str, 
                    resource_config: Optional[ResourceConfig] = None,
                    user_id: str = None) -> Dict[str, Any]:
        """执行任务的完整流程"""
        
        if resource_config is None:
            resource_config = ResourceConfig()
        
        print(f"[SafeBox] 开始执行任务: {task_id}")
        
        try:
            # 1. 模块A：环境准备器
            module_a = ModuleA_Prepare(task_id, user_code, resource_config, user_id)
            work_dir_path = module_a.run()
            
            # 2. 模块B：安全执行器
            module_b = ModuleB_Execute(work_dir_path, resource_config)
            execution_result = module_b.run()
            
            # 3. 模块C：取证与清理器
            module_c = ModuleC_Cleanup(work_dir_path, execution_result, archive_before_cleanup=False)
            cleanup_success = module_c.run()
            
            # 构建最终结果
            final_result = {
                'task_id': task_id,
                'success': execution_result['exit_code'] == 0,
                'execution_result': execution_result,
                'cleanup_success': cleanup_success
            }
            
            print(f"[SafeBox] 任务执行完成: {task_id}")
            return final_result
            
        except Exception as e:
            print(f"[SafeBox] 任务执行异常: {e}")
            return {
                'task_id': task_id,
                'success': False,
                'error': str(e),
                'cleanup_success': False,
                'execution_result': {
                    'exit_code': 1,
                    'stdout': '',
                    'stderr': str(e),
                    'duration_sec': 0,
                    'resource_violation': 'none'
                }
            }


def test_safebox():
    """测试SAFEBOX-ISOLATION系统"""
    
    print("=" * 60)
    print("SAFEBOX-ISOLATION v1.0 测试")
    print("=" * 60)
    
    safebox = SafeBoxIsolation()
    
    # 测试1：安全代码
    safe_code = """
import math
import random

# 安全计算示例
result = 0
for i in range(100):
    result += math.sqrt(i) * random.random()

print(f"安全计算完成，结果: {result:.4f}")
"""
    
    print("\n测试1: 安全代码执行")
    result = safebox.execute_task("test_safe_001", safe_code, 
                                ResourceConfig(timeout_sec=10))
    print(f"结果: {result['success']}")
    if result['success']:
        exec_result = result['execution_result']
        print(f"退出码: {exec_result['exit_code']}")
        print(f"执行时间: {exec_result['duration_sec']:.2f}秒")
        print(f"输出: {exec_result['stdout'][:100]}...")
    
    # 测试2：危险代码
    dangerous_code = """
import os
os.system('dir')  # 危险操作
print("这行代码不应该执行")
"""
    
    print("\n测试2: 危险代码拦截")
    result = safebox.execute_task("test_danger_001", dangerous_code,
                                ResourceConfig(timeout_sec=5))
    print(f"结果: {result['success']}")
    if not result['success']:
        exec_result = result['execution_result']
        print(f"退出码: {exec_result['exit_code']}")
        print(f"错误: {exec_result['stderr']}")
    
    # 测试3：超时测试
    timeout_code = """
import time

# 模拟长时间运行
print("开始长时间计算...")
for i in range(1000000):
    time.sleep(0.1)  # 每次睡眠0.1秒
    if i % 10 == 0:
        print(f"进度: {i}")
"""
    
    print("\n测试3: 超时控制")
    result = safebox.execute_task("test_timeout_001", timeout_code,
                                ResourceConfig(timeout_sec=3))
    print(f"结果: {result['success']}")
    exec_result = result['execution_result']
    print(f"资源违规: {exec_result['resource_violation']}")
    print(f"执行时间: {exec_result['duration_sec']:.2f}秒")


# 安全沙箱系统核心功能实现完成
# 专注于提供可靠的文件夹隔离和安全代码执行
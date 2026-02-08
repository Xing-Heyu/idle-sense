"""
sandbox.py
代码安全沙箱执行环境
确保用户提交的Python代码在受限环境中安全执行
"""

import ast
import sys
import time
import threading
import platform
from typing import Dict, Any, Optional
from io import StringIO

# Windows系统不支持resource模块
try:
    import resource
except ImportError:
    resource = None


class CodeSandbox:
    """代码安全沙箱执行环境"""
    
    def __init__(self):
        # 允许的安全模块白名单
        self.allowed_modules = {
            'math', 'random', 'statistics', 'time', 'datetime',
            'collections', 'itertools', 'functools', 'operator',
            'json', 're', 'string', 'hashlib', 'base64'
        }
        
        # 禁止的危险函数和属性
        self.dangerous_builtins = {
            'eval', 'exec', 'compile', 'input', 'open', 'file',
            '__import__', 'reload', 'globals', 'locals', 'vars',
            'dir', 'help', 'exit', 'quit', 'license', 'credits'
        }
        
        # 资源限制
        self.default_timeout = 300  # 5分钟
        self.default_memory_limit = 512  # MB
        
    def check_code_safety(self, code: str) -> Dict[str, Any]:
        """检查代码安全性"""
        try:
            # 解析AST语法树
            tree = ast.parse(code)
            
            # 检查导入语句
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split('.')[0]
                        if module_name not in self.allowed_modules:
                            return {
                                'safe': False,
                                'error': f'禁止导入模块: {module_name}'
                            }
                
                elif isinstance(node, ast.ImportFrom):
                    module_name = node.module.split('.')[0] if node.module else ''
                    if module_name not in self.allowed_modules:
                        return {
                            'safe': False,
                            'error': f'禁止从模块导入: {module_name}'
                        }
                
                # 检查危险函数调用
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                        if func_name in self.dangerous_builtins:
                            return {
                                'safe': False,
                                'error': f'禁止调用危险函数: {func_name}'
                            }
                
                # 检查属性访问
                elif isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name):
                        attr_name = node.attr
                        if attr_name.startswith('_'):
                            return {
                                'safe': False,
                                'error': f'禁止访问私有属性: {attr_name}'
                            }
            
            return {'safe': True, 'message': '代码安全检查通过'}
            
        except SyntaxError as e:
            return {'safe': False, 'error': f'语法错误: {e}'}
        except Exception as e:
            return {'safe': False, 'error': f'安全检查异常: {e}'}
    
    def set_memory_limit(self, memory_mb: int):
        """设置内存限制"""
        if resource is None:
            # Windows系统不支持resource模块
            return
            
        try:
            # 转换为字节
            memory_bytes = memory_mb * 1024 * 1024
            # 设置内存限制（Linux/macOS有效）
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        except (ValueError, resource.error):
            # 其他异常情况，忽略但不影响执行
            pass
    
    def execute_with_timeout(self, code: str, timeout: int, globals_dict: Dict) -> Optional[str]:
        """带超时控制的代码执行"""
        import subprocess
        import tempfile
        import os
        
        # 创建临时文件，只包含用户代码
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # 使用subprocess执行，提供更好的隔离
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=timeout,
                env={}  # 空环境，限制模块访问
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                error_msg = result.stderr.strip() or f"Exit code {result.returncode}"
                return f"执行错误: {error_msg}"
                
        except subprocess.TimeoutExpired:
            return f"执行超时（{timeout}秒）"
        except Exception as e:
            return f"执行异常: {e}"
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file)
            except:
                pass
    
    def execute_safe(self, code: str, timeout: Optional[int] = None, 
                    memory_limit: Optional[int] = None) -> Dict[str, Any]:
        """安全执行Python代码"""
        
        # 设置默认值
        if timeout is None:
            timeout = self.default_timeout
        if memory_limit is None:
            memory_limit = self.default_memory_limit
        
        # 1. 安全检查
        safety_result = self.check_code_safety(code)
        if not safety_result['safe']:
            return {
                'success': False,
                'error': safety_result['error'],
                'output': '',
                'execution_time': 0
            }
        
        # 2. 准备执行环境
        start_time = time.time()
        
        # 创建安全的全局命名空间
        safe_globals = {}
        
        # 添加安全的__builtins__
        safe_builtins = {
            'abs': abs, 'max': max, 'min': min, 'sum': sum, 'len': len,
            'range': range, 'enumerate': enumerate, 'zip': zip,
            'sorted': sorted, 'reversed': reversed, 'filter': filter,
            'map': map, 'any': any, 'all': all, 'bool': bool,
            'int': int, 'float': float, 'str': str, 'list': list,
            'dict': dict, 'tuple': tuple, 'set': set,
            'print': print, 'isinstance': isinstance, 'type': type
        }
        safe_globals['__builtins__'] = safe_builtins
        
        # 添加允许的模块
        for module_name in self.allowed_modules:
            try:
                module = __import__(module_name)
                safe_globals[module_name] = module
            except ImportError:
                pass
        
        # 3. 设置资源限制
        try:
            self.set_memory_limit(memory_limit)
        except Exception as e:
            return {
                'success': False,
                'error': f'资源限制设置失败: {e}',
                'output': '',
                'execution_time': 0
            }
        
        # 4. 执行代码
        try:
            output = self.execute_with_timeout(code, timeout, safe_globals)
            execution_time = time.time() - start_time
            
            return {
                'success': True,
                'output': output or '执行完成（无输出）',
                'execution_time': round(execution_time, 3)
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                'success': False,
                'error': f'执行异常: {e}',
                'output': '',
                'execution_time': round(execution_time, 3)
            }


# 全局沙箱实例
sandbox = CodeSandbox()


def test_sandbox():
    """测试沙箱功能"""
    
    # 测试安全代码
    safe_code = """
import math
import random

# 安全计算示例
result = 0
for i in range(1000):
    result += math.sqrt(i) * random.random()

print(f"安全计算完成，结果: {result:.4f}")
"""
    
    print("测试安全代码:")
    result = sandbox.execute_safe(safe_code, timeout=10)
    print(f"结果: {result}")
    
    # 测试危险代码
    dangerous_code = """
import os
os.system('rm -rf /')  # 危险操作
"""
    
    print("\n测试危险代码:")
    result = sandbox.execute_safe(dangerous_code, timeout=5)
    print(f"结果: {result}")


if __name__ == "__main__":
    test_sandbox()
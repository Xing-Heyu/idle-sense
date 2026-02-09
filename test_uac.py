#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试UAC权限请求脚本
专门测试UAC权限请求是否正常工作
"""

import os
import sys
import ctypes
import tempfile
import time

def is_admin():
    """检查当前是否有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def test_uac_request():
    """测试UAC权限请求"""
    print("=" * 50)
    print("测试UAC权限请求")
    print("=" * 50)
    
    # 检查当前权限
    if is_admin():
        print("当前已以管理员权限运行")
        print("为了测试UAC权限请求，请以普通用户权限重新运行此脚本")
        return
    
    print("当前以普通用户权限运行")
    print()
    
    # 尝试在需要管理员权限的路径创建文件
    test_path = "C:\\Windows\\idle_sense_test_uac"
    
    print(f"尝试在 {test_path} 创建测试文件...")
    
    try:
        os.makedirs(test_path, exist_ok=True)
        test_file = os.path.join(test_path, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        print("✅ 成功创建文件，当前已有足够权限")
        
        # 清理
        os.remove(test_file)
        os.rmdir(test_path)
        return
    
    except PermissionError:
        print("❌ 权限不足，需要UAC权限请求")
    
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        return
    
    # 创建临时脚本用于权限请求
    temp_script = os.path.join(tempfile.gettempdir(), "test_uac.py")
    script_content = f"""
import os
import sys
import ctypes

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if __name__ == "__main__":
    if not is_admin():
        print("ERROR: 未获取管理员权限")
        sys.exit(1)
    
    test_path = r"{test_path}"
    try:
        os.makedirs(test_path, exist_ok=True)
        test_file = os.path.join(test_path, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        print("SUCCESS: 使用管理员权限成功创建文件")
        
        # 清理
        os.remove(test_file)
        os.rmdir(test_path)
    except Exception as admin_err:
        print(f"ERROR: {{admin_err}}")
        sys.exit(1)
"""
    
    try:
        with open(temp_script, 'w', encoding='utf-8') as f:
            f.write(script_content)
    except Exception as e:
        print(f"❌ 创建临时脚本失败: {e}")
        return
    
    print("\n正在请求UAC权限...")
    print("请注意弹出的UAC权限请求对话框，并点击'是'")
    
    # 使用ShellExecute请求UAC权限
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, temp_script, None, 1
    )
    
    # 清理临时脚本
    try:
        import threading
        def delete_script():
            time.sleep(3)
            try:
                os.remove(temp_script)
            except:
                pass
        threading.Thread(target=delete_script, daemon=True).start()
    except:
        pass
    
    if result > 32:
        print("✅ UAC权限请求已发送")
        print("如果点击了'是'，应该会看到管理员权限创建文件成功的消息")
    else:
        print("❌ UAC权限请求失败，用户可能取消了操作")

if __name__ == "__main__":
    test_uac_request()
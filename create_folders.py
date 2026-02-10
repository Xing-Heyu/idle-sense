#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件夹创建脚本
用于创建闲置计算加速器系统所需的文件夹结构
"""

import os
import sys
import json
import argparse
import ctypes
import time
from datetime import datetime

def is_admin():
    """检查当前是否有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def check_write_permission(path):
    """检查指定路径是否有写入权限"""
    try:
        # 尝试创建测试文件
        test_file = os.path.join(path, ".permission_test")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        return True
    except (PermissionError, OSError):
        return False

def check_write_permission(target_path):
    """验证目标路径是否具备写入权限"""
    try:
        # 尝试创建一个临时文件来验证权限
        temp_file = os.path.join(target_path, "temp_permission_check.tmp")
        with open(temp_file, "w") as f:
            f.write("test")
        os.remove(temp_file)
        return True
    except (PermissionError, OSError):
        return False

def request_uac_elevation(target_path):
    """发起UAC提权请求，以管理员身份重启当前脚本"""
    if not is_admin():
        # 创建临时脚本用于权限请求
        temp_script = os.path.join(os.path.dirname(__file__), "temp_create_folders.py")
        
        # 转义路径中的特殊字符
        escaped_path = target_path.replace('\\', '\\\\')
        
        with open(temp_script, 'w', encoding='utf-8') as f:
            f.write(f"""
import os
import sys
import ctypes
import json

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def check_write_permission(target_path):
    try:
        temp_file = os.path.join(target_path, "temp_permission_check.tmp")
        with open(temp_file, "w") as f:
            f.write("test")
        os.remove(temp_file)
        return True
    except (PermissionError, OSError):
        return False

def create_folder_structure(base_path, user_id):
    try:
        # 创建三层平级文件夹结构
        user_system_dir = os.path.join(base_path, "user_system (系统专用-请勿修改)", user_id)
        user_data_dir = os.path.join(base_path, "user_data (您的数据文件-主要工作区)")
        temp_data_dir = os.path.join(base_path, "temp_data (临时文件-自动清理)")
        docs_dir = os.path.join(user_system_dir, "docs (说明文档)")
        
        os.makedirs(user_system_dir, exist_ok=True)
        os.makedirs(user_data_dir, exist_ok=True)
        os.makedirs(temp_data_dir, exist_ok=True)
        os.makedirs(docs_dir, exist_ok=True)
        
        return True, {{
            "user_system_dir": user_system_dir,
            "user_data_dir": user_data_dir,
            "temp_data_dir": temp_data_dir,
            "docs_dir": docs_dir
        }}
    except Exception as e:
        return False, {{"error": str(e)}}

if __name__ == "__main__":
    if not is_admin():
        print("ERROR: 未获取管理员权限")
        sys.exit(1)
    
    target_path = r"{escaped_path}"
    user_id = "temp_user_id"  # 临时用户ID，仅用于测试权限
    
    if not check_write_permission(os.path.dirname(target_path)):
        print("ERROR: 权限验证失败")
        sys.exit(1)
    
    success, result = create_folder_structure(target_path, user_id)
    if success:
        # 创建成功，删除测试文件夹
        import shutil
        try:
            shutil.rmtree(os.path.join(target_path, "user_system (系统专用-请勿修改)"))
            os.rmdir(os.path.join(target_path, "user_data (您的数据文件-主要工作区)"))
            os.rmdir(os.path.join(target_path, "temp_data (临时文件-自动清理)"))
        except:
            pass
        print("SUCCESS: 权限验证成功")
    else:
        print(f"ERROR: {result.get('error', '未知错误')}")
        sys.exit(1)
""")
        
        # 使用ShellExecute请求UAC权限
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, temp_script, None, 1
        )
        
        # 清理临时脚本
        try:
            # 延迟删除，确保脚本执行完成
            import threading
            def delete_script():
                import time
                time.sleep(3)
                try:
                    os.remove(temp_script)
                except:
                    pass
            threading.Thread(target=delete_script, daemon=True).start()
        except:
            pass
        
        if result > 32:
            # 等待用户响应UAC提示
            import time
            time.sleep(2)
            return True, "权限请求已发送，请确认UAC提示"
        else:
            return False, "权限请求失败，用户可能取消了操作"
    else:
        return True, "已有管理员权限"

def create_system_info_file(user_id, username, folder_location):
    """创建系统信息文件和文件夹结构 - 使用UAC权限请求"""
    result = {
        "success": False,
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "folder_location": folder_location
    }
    
    # 只存储系统需要的最小信息
    system_info = {
        "user_id": user_id,
        "username": username,
        "purpose": "此文件包含闲置计算加速器系统运行所需的信息，请勿删除"
    }
    
    # 根据用户选择的文件夹位置确定路径
    if folder_location == "project":
        base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "node_data")
    elif folder_location == "c":
        base_path = "C:\\idle-sense-system-data"
    elif folder_location == "d":
        base_path = "D:\\idle-sense-system-data"
    else:
        base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "node_data")
    
    result["base_path"] = base_path
    
    # 检查是否需要管理员权限
    needs_admin = False
    if folder_location in ["c", "d"]:
        needs_admin = True
    
    # 首先尝试直接创建
    try:
        os.makedirs(base_path, exist_ok=True)
        # 测试写入权限
        test_file = os.path.join(base_path, ".permission_test")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        direct_creation = True
    except (PermissionError, OSError):
        direct_creation = False
    
    if not direct_creation and needs_admin:
        # 请求UAC权限
        print("正在请求管理员权限以创建系统文件夹...")
        success, message = request_uac_elevation(base_path)
        
        if not success:
            result["error"] = message
            result["suggestion"] = "请确认UAC权限请求或选择其他位置"
            return result
        
        # 等待权限请求完成
        print("等待权限请求完成...")
        time.sleep(3)
        
        # 再次检查权限
        if not check_write_permission(base_path):
            result["error"] = "权限请求后仍无法创建文件夹"
            result["suggestion"] = "用户可能拒绝了权限请求，请重试或选择其他位置"
            return result
    elif not direct_creation and not needs_admin:
        # 非系统盘但权限不足
        result["error"] = "无法创建文件夹，权限不足"
        result["suggestion"] = "请选择其他位置或手动创建文件夹"
        return result
    
    # 创建三层平级文件夹结构
    user_system_dir = os.path.join(base_path, "user_system (系统专用-请勿修改)", user_id)  # 存放用户ID等系统数据
    user_data_dir = os.path.join(base_path, "user_data (您的数据文件-主要工作区)")               # 用户存放读写数据的地方
    temp_data_dir = os.path.join(base_path, "temp_data (临时文件-自动清理)")               # 临时存放数据给别人调用
    docs_dir = os.path.join(user_system_dir, "docs (说明文档)")                   # 存放说明文档
    
    result["user_system_dir"] = user_system_dir
    result["user_data_dir"] = user_data_dir
    result["temp_data_dir"] = temp_data_dir
    result["docs_dir"] = docs_dir
    
    try:
        os.makedirs(user_system_dir, exist_ok=True)
        os.makedirs(user_data_dir, exist_ok=True)
        os.makedirs(temp_data_dir, exist_ok=True)
        os.makedirs(docs_dir, exist_ok=True)
    except Exception as e:
        result["error"] = f"创建子文件夹失败: {str(e)}"
        result["suggestion"] = "请检查磁盘空间或权限设置"
        return result
    
    # 创建系统信息文件（在user_system文件夹中）
    system_file_path = os.path.join(user_system_dir, "system_info.json")
    result["system_file"] = system_file_path
    
    try:
        with open(system_file_path, "w", encoding="utf-8") as f:
            json.dump(system_info, f, ensure_ascii=False, indent=2)
    except Exception as e:
        result["error"] = f"创建系统信息文件失败: {str(e)}"
        result["suggestion"] = "请检查文件系统权限"
        return result
    
    # 所有操作成功
    result["success"] = True
    result["message"] = "文件夹和系统信息文件创建成功"
    return result

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='创建闲置计算加速器系统文件夹')
    parser.add_argument('--user-id', required=True, help='用户ID')
    parser.add_argument('--username', required=True, help='用户名')
    parser.add_argument('--folder-location', required=True, choices=['project', 'c', 'd'], help='文件夹位置')
    parser.add_argument('--output', required=True, help='输出结果的JSON文件路径')
    
    args = parser.parse_args()
    
    # 创建文件夹和系统信息文件（移除管理员权限硬性要求）
    result = create_system_info_file(args.user_id, args.username, args.folder_location)
    
    # 保存结果到输出文件
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"无法保存结果文件: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 输出结果到控制台（用于调试）
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 返回适当的退出码
    sys.exit(0 if result["success"] else 1)

if __name__ == "__main__":
    main()
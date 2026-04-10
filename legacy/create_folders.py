#!/usr/bin/env python3
"""
文件夹创建脚本
用于创建闲置计算加速器系统所需的文件夹结构
"""

import argparse
import contextlib
import ctypes
import json
import os
import sys
import time
from datetime import datetime


def is_admin():
    """检查当前是否有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except (AttributeError, OSError):
        return False


def check_write_permission(target_path):
    """验证目标路径是否具备写入权限"""
    try:
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
        temp_script = os.path.join(os.path.dirname(__file__), "temp_create_folders.py")
        escaped_path = target_path.replace("\\", "\\\\")

        with open(temp_script, "w", encoding="utf-8") as f:
            f.write(f"""
import os
import sys
import ctypes
import json

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except (AttributeError, OSError):
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
    user_id = "temp_user_id"

    if not check_write_permission(os.path.dirname(target_path)):
        print("ERROR: 权限验证失败")
        sys.exit(1)

    success, result = create_folder_structure(target_path, user_id)
    if success:
        import shutil
        with contextlib.suppress(Exception):
            shutil.rmtree(os.path.join(target_path, "user_system (系统专用-请勿修改)"))
            os.rmdir(os.path.join(target_path, "user_data (您的数据文件-主要工作区)"))
            os.rmdir(os.path.join(target_path, "temp_data (临时文件-自动清理)"))
        print("SUCCESS: 权限验证成功")
    else:
        print(f"ERROR: {{result.get('error', '未知错误')}}")
        sys.exit(1)
""")

        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, temp_script, None, 1
        )

        with contextlib.suppress(Exception):
            import threading

            def delete_script():
                import time

                time.sleep(3)
                with contextlib.suppress(BaseException):
                    os.remove(temp_script)

            threading.Thread(target=delete_script, daemon=True).start()

        if result > 32:
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
        "folder_location": folder_location,
    }

    system_info = {
        "user_id": user_id,
        "username": username,
        "purpose": "此文件包含闲置计算加速器系统运行所需的信息，请勿删除",
    }

    if folder_location == "project":
        base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "node_data")
    elif folder_location == "c":
        base_path = "C:\\idle-sense-system-data"
    elif folder_location == "d":
        base_path = "D:\\idle-sense-system-data"
    else:
        base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "node_data")

    result["base_path"] = base_path

    needs_admin = folder_location in ["c", "d"]

    try:
        os.makedirs(base_path, exist_ok=True)
        test_file = os.path.join(base_path, ".permission_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        direct_creation = True
    except (PermissionError, OSError):
        direct_creation = False

    if not direct_creation and needs_admin:
        print("正在请求管理员权限以创建系统文件夹...")
        success, message = request_uac_elevation(base_path)

        if not success:
            result["error"] = message
            result["suggestion"] = "请确认UAC权限请求或选择其他位置"
            return result

        print("等待权限请求完成...")
        time.sleep(3)

        if not check_write_permission(base_path):
            result["error"] = "权限请求后仍无法创建文件夹"
            result["suggestion"] = "用户可能拒绝了权限请求，请重试或选择其他位置"
            return result
    elif not direct_creation and not needs_admin:
        result["error"] = "无法创建文件夹，权限不足"
        result["suggestion"] = "请选择其他位置或手动创建文件夹"
        return result

    user_system_dir = os.path.join(base_path, "user_system (系统专用-请勿修改)", user_id)
    user_data_dir = os.path.join(base_path, "user_data (您的数据文件-主要工作区)")
    temp_data_dir = os.path.join(base_path, "temp_data (临时文件-自动清理)")
    docs_dir = os.path.join(user_system_dir, "docs (说明文档)")

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

    system_file_path = os.path.join(user_system_dir, "system_info.json")
    result["system_file"] = system_file_path

    try:
        with open(system_file_path, "w", encoding="utf-8") as f:
            json.dump(system_info, f, ensure_ascii=False, indent=2)
    except Exception as e:
        result["error"] = f"创建系统信息文件失败: {str(e)}"
        result["suggestion"] = "请检查文件系统权限"
        return result

    result["success"] = True
    result["message"] = "文件夹和系统信息文件创建成功"
    return result


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="创建闲置计算加速器系统文件夹")
    parser.add_argument("--user-id", required=True, help="用户ID")
    parser.add_argument("--username", required=True, help="用户名")
    parser.add_argument(
        "--folder-location", required=True, choices=["project", "c", "d"], help="文件夹位置"
    )
    parser.add_argument("--output", required=True, help="输出结果的JSON文件路径")

    args = parser.parse_args()

    result = create_system_info_file(args.user_id, args.username, args.folder_location)

    try:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"无法保存结果文件: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()

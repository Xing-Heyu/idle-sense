#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试注册流程脚本
模拟普通用户在网页上注册的完整流程，包括UAC权限请求
"""

import os
import sys
import json
import subprocess
import tempfile
import time
from datetime import datetime

def test_registration_flow():
    """测试完整的注册流程"""
    print("=" * 50)
    print("测试闲置计算加速器注册流程")
    print("=" * 50)
    
    # 模拟用户输入
    test_username = "测试用户123"
    test_user_id = f"user_{int(time.time())}"  # 生成唯一用户ID
    test_folder_location = "c"  # 测试C盘创建，这会触发UAC权限请求
    
    print(f"测试用户名: {test_username}")
    print(f"测试用户ID: {test_user_id}")
    print(f"选择的文件夹位置: {test_folder_location}")
    print()
    
    # 调用create_folders.py脚本
    print("正在调用create_folders.py脚本...")
    
    # 创建临时文件用于存储结果
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        temp_output_path = temp_file.name
    
    try:
        # 构建命令
        script_path = os.path.join(os.path.dirname(__file__), "create_folders.py")
        cmd = [
            sys.executable,
            script_path,
            "--user-id", test_user_id,
            "--username", test_username,
            "--folder-location", test_folder_location,
            "--output", temp_output_path
        ]
        
        print(f"执行命令: {' '.join(cmd)}")
        print()
        print("注意: 如果选择C盘或D盘，应该会弹出UAC权限请求对话框")
        print("请在对话框中点击'是'以允许权限")
        print()
        
        # 执行命令
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        end_time = time.time()
        
        print(f"命令执行完成，耗时: {end_time - start_time:.2f}秒")
        print(f"返回码: {result.returncode}")
        print()
        
        # 显示输出
        if result.stdout:
            print("标准输出:")
            print(result.stdout)
        
        if result.stderr:
            print("错误输出:")
            print(result.stderr)
        
        # 读取结果文件
        if os.path.exists(temp_output_path):
            with open(temp_output_path, 'r', encoding='utf-8') as f:
                result_data = json.load(f)
            
            print("\n结果文件内容:")
            print(json.dumps(result_data, ensure_ascii=False, indent=2))
            
            # 验证结果
            print("\n验证结果:")
            if result_data.get("success"):
                print("✅ 注册流程成功!")
                
                # 检查文件夹是否创建
                base_path = result_data.get("base_path")
                if base_path and os.path.exists(base_path):
                    print(f"✅ 基础文件夹已创建: {base_path}")
                    
                    # 检查子文件夹
                    user_system_dir = result_data.get("user_system_dir")
                    user_data_dir = result_data.get("user_data_dir")
                    temp_data_dir = result_data.get("temp_data_dir")
                    
                    if user_system_dir and os.path.exists(user_system_dir):
                        print(f"✅ 用户系统文件夹已创建: {user_system_dir}")
                    else:
                        print(f"❌ 用户系统文件夹未创建: {user_system_dir}")
                    
                    if user_data_dir and os.path.exists(user_data_dir):
                        print(f"✅ 用户数据文件夹已创建: {user_data_dir}")
                    else:
                        print(f"❌ 用户数据文件夹未创建: {user_data_dir}")
                    
                    if temp_data_dir and os.path.exists(temp_data_dir):
                        print(f"✅ 临时数据文件夹已创建: {temp_data_dir}")
                    else:
                        print(f"❌ 临时数据文件夹未创建: {temp_data_dir}")
                    
                    # 检查系统信息文件
                    system_file = result_data.get("system_file")
                    if system_file and os.path.exists(system_file):
                        print(f"✅ 系统信息文件已创建: {system_file}")
                        
                        # 读取并显示系统信息文件内容
                        with open(system_file, 'r', encoding='utf-8') as f:
                            system_info = json.load(f)
                        print("系统信息文件内容:")
                        print(json.dumps(system_info, ensure_ascii=False, indent=2))
                    else:
                        print(f"❌ 系统信息文件未创建: {system_file}")
                else:
                    print(f"❌ 基础文件夹未创建: {base_path}")
            else:
                print("❌ 注册流程失败!")
                error = result_data.get("error", "未知错误")
                suggestion = result_data.get("suggestion", "")
                print(f"错误: {error}")
                if suggestion:
                    print(f"建议: {suggestion}")
        else:
            print("❌ 结果文件未创建，可能脚本执行失败")
    
    except subprocess.TimeoutExpired:
        print("❌ 命令执行超时，可能UAC权限请求未被处理")
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
    finally:
        # 清理临时文件
        try:
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
        except:
            pass
    
    print("\n测试完成")

if __name__ == "__main__":
    test_registration_flow()
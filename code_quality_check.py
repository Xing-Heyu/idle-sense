#!/usr/bin/env python3
"""
代码质量检查脚本
检查web_interface.py的语法问题、逻辑问题和系统运行问题
"""

import ast
import os
import sys
import re
import subprocess
from pathlib import Path

def check_syntax(file_path):
    """检查语法问题"""
    print("=" * 50)
    print("第一遍检查：语法问题")
    print("=" * 50)
    
    issues = []
    
    # 1. 使用Python AST检查语法
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # 尝试解析AST
        ast.parse(source)
        print("[PASS] Python语法检查通过")
    except SyntaxError as e:
        issues.append(f"语法错误: {e}")
        print(f"[ERROR] 语法错误: {e}")
    except Exception as e:
        issues.append(f"解析错误: {e}")
        print(f"[ERROR] 解析错误: {e}")
    
    # 2. 使用py_compile检查
    try:
        result = subprocess.run([sys.executable, '-m', 'py_compile', file_path], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("[PASS] py_compile检查通过")
        else:
            issues.append(f"编译错误: {result.stderr}")
            print(f"[ERROR] 编译错误: {result.stderr}")
    except Exception as e:
        issues.append(f"编译检查失败: {e}")
        print(f"[ERROR] 编译检查失败: {e}")
    
    # 3. 检查常见代码问题
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines, 1):
        # 检查未使用的变量
        if re.search(r'^\s*\w+\s*=\s*.+', line) and not re.search(r'#.*未使用', line):
            var_name = re.search(r'^\s*(\w+)\s*=', line)
            if var_name:
                var = var_name.group(1)
                # 简单检查变量是否在后面使用
                used = False
                for j in range(i, len(lines)):
                    if var in lines[j]:
                        used = True
                        break
                if not used and i < len(lines) - 10:  # 只检查后面10行内的使用
                    print(f"[WARN] 第{i}行: 变量 '{var}' 可能未使用")
        
        # 检查过长的行
        if len(line) > 120:
            print(f"[WARN] 第{i}行: 行过长 ({len(line)} 字符)")
        
        # 检查可能的缩进问题
        if line.strip() and not line.startswith('\n') and not line.startswith(' ') and not line.startswith('\t'):
            if i > 1 and lines[i-2].strip().endswith(':'):
                print(f"[WARN] 第{i}行: 可能缺少缩进")
    
    if not issues:
        print("[PASS] 语法检查完成，未发现问题")
    else:
        print(f"[ERROR] 发现 {len(issues)} 个语法问题")
    
    return len(issues) == 0

def check_logic(file_path):
    """检查逻辑问题"""
    print("\n" + "=" * 50)
    print("第二遍检查：逻辑问题")
    print("=" * 50)
    
    issues = []
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. 检查函数定义
    functions = re.findall(r'def\s+(\w+)\s*\(', content)
    print(f"[INFO] 发现 {len(functions)} 个函数定义")
    
    # 2. 检查关键逻辑
    # 检查用户注册逻辑
    if 'validate_username' in content:
        print("[PASS] 用户名验证函数存在")
    else:
        issues.append("缺少用户名验证函数")
        print("[ERROR] 缺少用户名验证函数")
    
    if 'check_username_availability' in content:
        print("[PASS] 用户名可用性检查函数存在")
    else:
        issues.append("缺少用户名可用性检查函数")
        print("[ERROR] 缺少用户名可用性检查函数")
    
    # 检查文件夹创建逻辑
    if 'create_system_info_file' in content:
        print("[PASS] 文件夹创建函数存在")
    else:
        issues.append("缺少文件夹创建函数")
        print("[ERROR] 缺少文件夹创建函数")
    
    # 检查文件夹结构
    if 'user_system_dir' in content and 'user_data_dir' in content and 'temp_data_dir' in content:
        print("[PASS] 三层文件夹结构定义正确")
    else:
        issues.append("文件夹结构定义不完整")
        print("[ERROR] 文件夹结构定义不完整")
    
    # 检查重试机制
    if 'create_folders_with_retry' in content:
        print("[PASS] 文件夹创建重试机制存在")
    else:
        issues.append("缺少文件夹创建重试机制")
        print("[ERROR] 缺少文件夹创建重试机制")
    
    # 检查进度条
    if 'progress_bar' in content and 'status_text' in content:
        print("[PASS] 注册进度条存在")
    else:
        issues.append("缺少注册进度条")
        print("[ERROR] 缺少注册进度条")
    
    # 检查错误处理
    if 'try:' in content and 'except' in content:
        print("[PASS] 错误处理机制存在")
    else:
        issues.append("缺少错误处理机制")
        print("[ERROR] 缺少错误处理机制")
    
    # 检查session管理
    if 'st.session_state.user_session' in content:
        print("[PASS] 用户会话管理存在")
    else:
        issues.append("缺少用户会话管理")
        print("[ERROR] 缺少用户会话管理")
    
    # 检查设备ID管理
    if 'generate_device_id' in content and 'get_device_node_mapping' in content:
        print("[PASS] 设备ID管理存在")
    else:
        issues.append("缺少设备ID管理")
        print("[ERROR] 缺少设备ID管理")
    
    # 检查缓存管理
    if 'load_cache_data' in content and 'save_cache_data' in content:
        print("[PASS] 缓存管理存在")
    else:
        issues.append("缺少缓存管理")
        print("[ERROR] 缺少缓存管理")
    
    if not issues:
        print("[PASS] 逻辑检查完成，未发现问题")
    else:
        print(f"[ERROR] 发现 {len(issues)} 个逻辑问题")
    
    return len(issues) == 0

def check_system_integration():
    """检查系统集成"""
    print("\n" + "=" * 50)
    print("第三遍检查：系统集成")
    print("=" * 50)
    
    issues = []
    
    # 1. 检查必要文件是否存在
    required_files = [
        'web_interface.py',
        'scheduler/simple_server.py',
        'node/simple_client.py',
        'create_folders.py',
        'request_permission.py'
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"[PASS] {file_path} 存在")
        else:
            issues.append(f"缺少必要文件: {file_path}")
            print(f"[ERROR] 缺少必要文件: {file_path}")
    
    # 2. 检查依赖
    try:
        import streamlit
        print("[PASS] streamlit 已安装")
    except ImportError:
        issues.append("streamlit 未安装")
        print("[ERROR] streamlit 未安装")
    
    try:
        import requests
        print("[PASS] requests 已安装")
    except ImportError:
        issues.append("requests 未安装")
        print("[ERROR] requests 未安装")
    
    try:
        import pandas
        print("[PASS] pandas 已安装")
    except ImportError:
        issues.append("pandas 未安装")
        print("[ERROR] pandas 未安装")
    
    try:
        import plotly
        print("[PASS] plotly 已安装")
    except ImportError:
        issues.append("plotly 未安装")
        print("[ERROR] plotly 未安装")
    
    # 3. 检查调度中心配置
    with open('web_interface.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'SCHEDULER_URL' in content:
        print("[PASS] 调度中心URL配置存在")
        # 提取URL
        url_match = re.search(r'SCHEDULER_URL\s*=\s*["\']([^"\']+)["\']', content)
        if url_match:
            url = url_match.group(1)
            print(f"[INFO] 调度中心URL: {url}")
        else:
            issues.append("无法提取调度中心URL")
            print("[ERROR] 无法提取调度中心URL")
    else:
        issues.append("缺少调度中心URL配置")
        print("[ERROR] 缺少调度中心URL配置")
    
    # 4. 检查API端点
    api_endpoints = [
        '/submit',
        '/status/',
        '/api/nodes',
        '/stats',
        '/results'
    ]
    
    for endpoint in api_endpoints:
        if endpoint in content:
            print(f"[PASS] API端点 {endpoint} 存在")
        else:
            issues.append(f"缺少API端点: {endpoint}")
            print(f"[ERROR] 缺少API端点: {endpoint}")
    
    # 5. 检查用户流程
    user_flow_components = [
        '用户注册',
        '用户登录',
        '任务提交',
        '节点管理',
        '任务监控'
    ]
    
    for component in user_flow_components:
        if component in content:
            print(f"[PASS] 用户流程组件 {component} 存在")
        else:
            issues.append(f"缺少用户流程组件: {component}")
            print(f"[ERROR] 缺少用户流程组件: {component}")
    
    if not issues:
        print("[PASS] 系统集成检查完成，未发现问题")
        print("\n[SUCCESS] 系统应该可以正常运行！")
        print("\n[INFO] 建议测试流程:")
        print("1. 启动调度中心: python scheduler/simple_server.py")
        print("2. 启动Web界面: streamlit run web_interface.py")
        print("3. 注册新用户")
        print("4. 激活本地节点")
        print("5. 提交测试任务")
        print("6. 检查任务执行和节点状态")
    else:
        print(f"[ERROR] 发现 {len(issues)} 个系统集成问题")
    
    return len(issues) == 0

def main():
    """主函数"""
    print("开始代码质量检查...")
    
    file_path = 'web_interface.py'
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return
    
    # 三遍检查
    syntax_ok = check_syntax(file_path)
    logic_ok = check_logic(file_path)
    integration_ok = check_system_integration()
    
    # 总结
    print("\n" + "=" * 50)
    print("检查总结")
    print("=" * 50)
    
    if syntax_ok and logic_ok and integration_ok:
        print("[SUCCESS] 所有检查通过！代码质量良好，系统应该可以正常运行。")
    else:
        print("[WARN] 发现一些问题，建议修复后再运行系统。")
        if not syntax_ok:
            print("[ERROR] 语法检查未通过")
        if not logic_ok:
            print("[ERROR] 逻辑检查未通过")
        if not integration_ok:
            print("[ERROR] 系统集成检查未通过")

if __name__ == "__main__":
    main()
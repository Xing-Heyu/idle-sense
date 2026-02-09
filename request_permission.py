#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
权限请求脚本
用于请求UAC权限并创建文件夹
"""

import os
import sys
import json
import argparse
from datetime import datetime

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='请求UAC权限并创建文件夹')
    parser.add_argument('folder_path', help='要创建的文件夹路径')
    
    args = parser.parse_args()
    
    try:
        # 创建文件夹
        os.makedirs(args.folder_path, exist_ok=True)
        
        # 测试写入权限
        test_file = os.path.join(args.folder_path, ".permission_test")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        
        # 创建结果文件
        result = {
            "success": True,
            "message": f"文件夹创建成功: {args.folder_path}",
            "timestamp": datetime.now().isoformat()
        }
        
        # 保存结果到临时文件
        result_file = os.path.join(args.folder_path, ".permission_result.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"文件夹创建成功: {args.folder_path}")
        return 0
        
    except Exception as e:
        # 创建错误结果
        result = {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        
        # 尝试保存错误结果
        try:
            result_file = os.path.join(os.path.dirname(args.folder_path), ".permission_result.json")
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except:
            pass
        
        print(f"文件夹创建失败: {str(e)}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
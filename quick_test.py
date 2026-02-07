#!/usr/bin/env python3
"""
快速测试脚本 - 验证系统功能
"""

import requests
import time

def simple_test():
    """简单测试任务"""
    
    # 简单的计算任务
    code = """
print("🎯 开始执行测试任务")

# 简单的数学计算
result = 0
for i in range(10000):
    result += i * 0.001

print(f"计算结果: {result:.2f}")

# 返回结果
__result__ = f"测试任务完成，计算结果: {result:.2f}"
print("✅ 任务执行完成")
"""

    print("🚀 提交测试任务...")
    
    try:
        response = requests.post(
            "http://localhost:8000/submit",
            json={"code": code},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            task_id = result.get('task_id')
            print(f"✅ 任务提交成功！任务ID: {task_id}")
            
            # 等待任务完成
            print("⏳ 等待任务执行...")
            
            for i in range(20):  # 最多等待60秒
                time.sleep(3)
                
                # 检查任务状态
                status_response = requests.get(f"http://localhost:8000/status/{task_id}")
                if status_response.status_code == 200:
                    task_info = status_response.json()
                    status = task_info.get('status')
                    
                    if status == 'completed':
                        print("🎉 任务执行完成！")
                        print(f"📝 结果: {task_info.get('result', '无结果')}")
                        return True
                    elif status == 'failed':
                        print("❌ 任务执行失败")
                        return False
                    else:
                        print(f"⏳ 任务状态: {status}")
                else:
                    print(f"⚠️ 无法获取任务状态: {status_response.status_code}")
            
            print("⏰ 任务执行超时")
            return False
            
        else:
            print(f"❌ 任务提交失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 提交任务时出错: {e}")
        return False

def check_system():
    """检查系统状态"""
    
    print("🔍 检查系统状态...")
    
    try:
        # 检查调度中心
        response = requests.get("http://localhost:8000/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 调度中心运行正常 (任务数: {data.get('task_count', 0)})")
        else:
            print("❌ 调度中心异常")
            return False
        
        # 检查节点
        response = requests.get("http://localhost:8000/api/nodes", timeout=5)
        if response.status_code == 200:
            nodes = response.json()
            print(f"✅ 在线节点: {nodes.get('count', 0)}")
        else:
            print("⚠️ 无法获取节点信息")
        
        return True
        
    except Exception as e:
        print(f"❌ 系统检查失败: {e}")
        return False

def main():
    """主函数"""
    
    print("=" * 50)
    print("⚡ 闲置计算加速器 - 快速测试")
    print("=" * 50)
    print()
    
    # 检查系统状态
    if not check_system():
        print("\n❌ 系统状态异常")
        return
    
    print("\n" + "=" * 50)
    
    # 执行测试
    success = simple_test()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 测试成功！系统运行正常")
    else:
        print("❌ 测试失败")
    print("=" * 50)

if __name__ == "__main__":
    main()
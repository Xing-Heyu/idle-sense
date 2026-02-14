#!/usr/bin/env python3
"""
简单测试脚本 - 验证系统基本功能
"""

import requests
import time

def test_system():
    print("🎯 测试闲置计算加速器系统")
    print("=" * 50)
    
    # 1. 检查调度中心
    print("1. 检查调度中心...")
    try:
        r = requests.get('http://localhost:8000/', timeout=5)
        if r.status_code == 200:
            data = r.json()
            print(f"   ✅ 调度中心运行正常")
            print(f"   📊 任务数: {data.get('task_count', 0)}")
        else:
            print(f"   ❌ 调度中心异常: {r.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ 无法连接到调度中心: {e}")
        return False
    
    # 2. 检查节点状态
    print("2. 检查节点状态...")
    try:
        r = requests.get('http://localhost:8000/api/nodes', timeout=5)
        if r.status_code == 200:
            nodes = r.json()
            count = nodes.get('count', 0)
            print(f"   ✅ 在线节点: {count}")
            if count == 0:
                print("   ⚠️  没有在线节点，任务无法执行")
        else:
            print(f"   ❌ 无法获取节点信息: {r.status_code}")
    except Exception as e:
        print(f"   ❌ 检查节点状态失败: {e}")
    
    # 3. 提交简单任务
    print("3. 提交测试任务...")
    
    code = """
# 简单的计算任务
result = 0
for i in range(1000):
    result += i * 0.01

# 返回结果
__result__ = f"计算完成，结果: {result:.2f}"
"""
    
    try:
        payload = {
            "code": code,
            "timeout": 30
        }
        
        response = requests.post('http://localhost:8000/submit', json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            task_id = result.get('task_id')
            print(f"   ✅ 任务提交成功")
            print(f"   📋 任务ID: {task_id}")
            
            # 等待任务完成
            print("4. 等待任务执行...")
            
            for i in range(10):  # 最多等待30秒
                time.sleep(3)
                
                try:
                    status_r = requests.get(f'http://localhost:8000/status/{task_id}', timeout=5)
                    if status_r.status_code == 200:
                        task_info = status_r.json()
                        status = task_info.get('status')
                        
                        if status == 'completed':
                            print(f"   🎉 任务执行完成！")
                            print(f"   📝 结果: {task_info.get('result', '无结果')}")
                            return True
                        elif status == 'failed':
                            print(f"   ❌ 任务执行失败")
                            return False
                        elif status in ['pending', 'assigned', 'running']:
                            print(f"   ⏳ 任务状态: {status}")
                        else:
                            print(f"   ❓ 未知状态: {status}")
                    else:
                        print(f"   ⚠️  无法获取任务状态: {status_r.status_code}")
                except Exception as e:
                    print(f"   ⚠️  查询任务状态失败: {e}")
            
            print("   ⏰ 任务等待超时")
            return False
            
        else:
            print(f"   ❌ 任务提交失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ 提交任务时出错: {e}")
        return False

def main():
    """主函数"""
    
    print("\n" + "=" * 50)
    print("⚡ 闲置计算加速器 - 系统测试")
    print("=" * 50)
    print()
    
    success = test_system()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 测试成功！系统可以正常使用")
    else:
        print("❌ 测试失败，请检查系统状态")
    
    print("=" * 50)
    
    # 提供使用建议
    print("\n💡 使用建议:")
    print("1. 确保节点客户端正在运行")
    print("2. 访问 http://localhost:8501 使用网页界面")
    print("3. 在网页界面提交更复杂的计算任务")
    print("4. 查看任务执行状态和结果")

if __name__ == "__main__":
    main()

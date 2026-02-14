#!/usr/bin/env python3
"""
测试任务提交 - 蒙特卡洛方法计算π
"""

import requests
import json
import time

def submit_monte_carlo_pi_task():
    """提交蒙特卡洛计算π的任务"""
    
    # 蒙特卡洛方法计算π的代码
    code = """
import random
import math
import time

def monte_carlo_pi(samples=1000000):
    \"\"\"蒙特卡洛方法计算π\"\"\"
    print("🎯 开始蒙特卡洛方法计算π")
    print(f"样本数: {samples:,}")
    
    start_time = time.time()
    
    inside_circle = 0
    for i in range(samples):
        x = random.random()
        y = random.random()
        
        if x*x + y*y <= 1.0:
            inside_circle += 1
        
        # 每10%进度显示一次
        if (i + 1) % (samples // 10) == 0:
            progress = (i + 1) / samples * 100
            print(f"进度: {progress:.0f}%")
    
    pi_estimate = 4.0 * inside_circle / samples
    error = abs(pi_estimate - math.pi)
    
    elapsed = time.time() - start_time
    
    print("\n📊 计算结果:")
    print(f"π的估计值: {pi_estimate:.10f}")
    print(f"真实π值: {math.pi:.10f}")
    print(f"误差: {error:.10f}")
    print(f"计算时间: {elapsed:.3f}秒")
    print(f"速度: {samples/elapsed:,.0f} 样本/秒")
    
    # 返回结果
    result = f"蒙特卡洛π估计: {pi_estimate:.10f}, 误差: {error:.10f}, 耗时: {elapsed:.3f}秒"
    return result

# 执行计算
samples = 500000  # 50万样本，适合测试
result = monte_carlo_pi(samples)
__result__ = result
"""

    # 提交任务到调度中心
    print("🚀 提交蒙特卡洛计算π任务...")
    
    payload = {
        "code": code,
        "timeout": 60,
        "resources": {
            "cpu": 1.0,
            "memory": 256
        }
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/submit",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            task_id = result.get('task_id')
            print(f"✅ 任务提交成功！任务ID: {task_id}")
            print(f"📋 任务详情: {result}")
            
            # 等待任务完成
            print("\n⏳ 等待任务执行...")
            return wait_for_task_completion(task_id)
        else:
            print(f"❌ 任务提交失败: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 提交任务时出错: {e}")
        return False

def wait_for_task_completion(task_id, timeout=120):
    """等待任务完成"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # 获取任务状态
            response = requests.get(f"http://localhost:8000/status/{task_id}", timeout=5)
            
            if response.status_code == 200:
                task_info = response.json()
                status = task_info.get('status', 'unknown')
                
                if status == 'completed':
                    print(f"\n🎉 任务完成！")
                    print(f"📝 执行结果:")
                    print(task_info.get('result', '无结果'))
                    return True
                elif status == 'failed':
                    print(f"❌ 任务执行失败")
                    return False
                elif status in ['pending', 'assigned', 'running']:
                    print(f"⏳ 任务状态: {status}")
                else:
                    print(f"❓ 未知状态: {status}")
            else:
                print(f"⚠️  获取任务状态失败: {response.status_code}")
        except Exception as e:
            print(f"⚠️  查询任务状态时出错: {e}")
        
        time.sleep(3)  # 每3秒查询一次
    
    print(f"⏰ 任务等待超时 ({timeout}秒)")
    return False

def check_system_status():
    """检查系统状态"""
    print("🔍 检查系统状态...")
    
    try:
        # 检查调度中心
        response = requests.get("http://localhost:8000/", timeout=5)
        if response.status_code == 200:
            print("✅ 调度中心运行正常")
        else:
            print("❌ 调度中心异常")
            return False
        
        # 检查节点状态
        response = requests.get("http://localhost:8000/api/nodes", timeout=5)
        if response.status_code == 200:
            nodes_info = response.json()
            node_count = nodes_info.get('count', 0)
            print(f"✅ 在线节点: {node_count}")
        else:
            print("❌ 无法获取节点信息")
        
        return True
        
    except Exception as e:
        print(f"❌ 系统状态检查失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("🎯 闲置计算加速器 - 蒙特卡洛π计算测试")
    print("=" * 60)
    print()
    
    # 检查系统状态
    if not check_system_status():
        print("\n❌ 系统状态异常，请确保调度中心和节点客户端已启动")
        print("💡 启动命令:")
        print("  1. 调度中心: python scheduler/simple_server.py")
        print("  2. 节点客户端: python node/simple_client.py")
        return
    
    print("\n" + "=" * 60)
    
    # 提交任务
    success = submit_monte_carlo_pi_task()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 测试成功！闲置计算加速器运行正常")
    else:
        print("❌ 测试失败，请检查系统状态")
    
    print("=" * 60)

if __name__ == "__main__":
    main()

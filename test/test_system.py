#!/usr/bin/env python3
"""
闲置计算加速器 - 系统测试脚本
测试各个组件是否能正常运行
"""

import sys
import time
import requests
import subprocess
from pathlib import Path

def test_scheduler():
    """测试调度中心"""
    print("🧪 测试调度中心...")
    
    # 启动调度中心
    try:
        process = subprocess.Popen(
            [sys.executable, "scheduler/simple_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 等待启动
        time.sleep(3)
        
        # 测试连接
        try:
            response = requests.get("http://localhost:8000/", timeout=5)
            if response.status_code == 200:
                print("✅ 调度中心测试通过")
                return True, process
            else:
                print(f"❌ 调度中心响应异常: {response.status_code}")
        except Exception as e:
            print(f"❌ 无法连接到调度中心: {e}")
        
        # 停止进程
        process.terminate()
        
    except Exception as e:
        print(f"❌ 调度中心启动失败: {e}")
    
    return False, None

def test_node_client():
    """测试节点客户端"""
    print("🧪 测试节点客户端...")
    
    try:
        # 直接导入测试
        sys.path.insert(0, str(Path(__file__).parent))
        from node.simple_client import NodeClient
        
        client = NodeClient()
        print("✅ 节点客户端导入成功")
        
        # 测试系统信息获取
        info = client._get_system_info()
        print(f"✅ 系统信息获取成功: {info.get('hostname', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 节点客户端测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_web_interface():
    """测试网页界面"""
    print("🧪 测试网页界面...")
    
    try:
        # 检查streamlit是否可用
        result = subprocess.run([sys.executable, "-c", "import streamlit; print('✅ streamlit可用')"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ streamlit依赖正常")
            
            # 检查网页界面代码
            sys.path.insert(0, str(Path(__file__).parent))
            import web_interface
            print("✅ 网页界面代码正常")
            
            return True
        else:
            print("❌ streamlit不可用")
            
    except Exception as e:
        print(f"❌ 网页界面测试失败: {e}")
        return False

def test_task_submission():
    """测试任务提交"""
    print("🧪 测试任务提交...")
    
    try:
        # 检查调度中心是否运行
        response = requests.get("http://localhost:8000/", timeout=5)
        if response.status_code != 200:
            print("⚠️  调度中心未运行，跳过任务提交测试")
            return True
        
        # 测试提交任务
        code = """
print("Hello from idle computer!")
result = 1 + 1
print(f"1+1={result}")
__result__ = result
"""
        
        response = requests.post(
            "http://localhost:8000/submit",
            json={"code": code}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 任务提交成功，任务ID: {result.get('task_id')}")
            return True
        else:
            print(f"❌ 任务提交失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 任务提交测试失败: {e}")
    
    return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("⚡ 闲置计算加速器 - 系统测试")
    print("=" * 60)
    
    # 切换到项目目录
    project_dir = Path(__file__).parent
    print(f"📁 项目目录: {project_dir}")
    
    results = []
    scheduler_process = None
    
    try:
        # 测试调度中心
        scheduler_ok, scheduler_process = test_scheduler()
        results.append(("调度中心", scheduler_ok))
        
        # 测试节点客户端
        node_ok = test_node_client()
        results.append(("节点客户端", node_ok))
        
        # 测试网页界面
        web_ok = test_web_interface()
        results.append(("网页界面", web_ok))
        
        # 测试任务提交
        if scheduler_ok:
            task_ok = test_task_submission()
            results.append(("任务提交", task_ok))
        
        # 显示测试结果
        print("\n" + "=" * 60)
        print("📊 测试结果汇总:")
        print("=" * 60)
        
        all_passed = True
        for component, passed in results:
            status = "✅ 通过" if passed else "❌ 失败"
            print(f"  {component}: {status}")
            if not passed:
                all_passed = False
        
        print("\n" + "=" * 60)
        if all_passed:
            print("🎉 所有测试通过！系统可以正常运行。")
            print("\n🚀 启动命令:")
            print("  1. 调度中心: python scheduler/simple_server.py")
            print("  2. 节点客户端: python node/simple_client.py") 
            print("  3. 网页界面: streamlit run web_interface.py")
        else:
            print("⚠️  部分测试失败，请检查错误信息。")
        
    finally:
        # 清理
        if scheduler_process:
            print("\n🛑 停止调度中心...")
            scheduler_process.terminate()
            scheduler_process.wait()
    
    print("=" * 60)

if __name__ == "__main__":
    main()

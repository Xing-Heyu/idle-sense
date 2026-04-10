#!/usr/bin/env python3
"""
scripts/quick_test.py
快速测试脚本 - 验证基本功能
"""

import sys
import time
from pathlib import Path

import requests

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def print_step(step, description):
    """打印步骤信息"""
    print(f"\n{'='*60}")
    print(f"步骤 {step}: {description}")
    print(f"{'='*60}")

def test_scheduler_connection(url="http://localhost:8000"):
    """测试调度中心连接"""
    print_step(1, "测试调度中心连接")

    try:
        response = requests.get(f"{url}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ 连接成功!")
            print(f"   服务: {data.get('service', 'N/A')}")
            print(f"   状态: {data.get('status', 'N/A')}")
            print(f"   版本: {data.get('version', 'N/A')}")
            return True
        else:
            print(f"❌ 连接失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 连接错误: {e}")
        print("   请确保调度中心正在运行: python scheduler/simple_server.py")
        return False

def test_idle_sense_library():
    """测试闲置检测库"""
    print_step(2, "测试闲置检测库")

    try:
        from idle_sense import core

        # 测试平台检测
        platform = core.get_platform()
        print(f"✅ 平台检测: {platform}")

        # 测试健康检查
        result = core.check_platform_module()
        success = result.get('loaded', False)
        message = result.get('error', 'OK') if not success else '模块加载成功'
        print(f"✅ 模块健康: {success} - {message}")

        # 测试基本功能
        status = core.get_system_status(idle_threshold_sec=5)
        print(f"✅ 获取系统状态: {len(status)} 个字段")

        is_idle = core.is_idle(idle_threshold_sec=5)
        print(f"✅ 闲置检测: {is_idle}")

        return True

    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return False

def test_task_submission(url="http://localhost:8000"):
    """测试任务提交"""
    print_step(3, "测试任务提交")

    # 简单计算任务
    test_code = """
result = 0
for i in range(1000):
    result += i * 0.001
__result__ = f"计算结果: {result:.4f}"
"""

    try:
        # 提交任务
        payload = {
            "code": test_code,
            "timeout": 30,
            "resources": {"cpu": 1.0, "memory": 512}
        }

        response = requests.post(f"{url}/submit", json=payload, timeout=10)

        if response.status_code == 200:
            data = response.json()
            task_id = data.get("task_id")
            print("✅ 任务提交成功!")
            print(f"   任务ID: {task_id}")
            print(f"   状态: {data.get('status', 'N/A')}")

            # 等待并检查状态
            return check_task_status(url, task_id)
        else:
            print(f"❌ 提交失败: HTTP {response.status_code}")
            print(f"   响应: {response.text}")
            return False

    except Exception as e:
        print(f"❌ 提交错误: {e}")
        return False

def check_task_status(url, task_id, max_attempts=10):
    """检查任务状态"""
    print(f"\n检查任务状态 (ID: {task_id})...")

    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{url}/status/{task_id}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")

                print(f"  尝试 {attempt+1}/{max_attempts}: 状态 = {status}")

                if status == "completed":
                    result = data.get("result", "无结果")
                    print("✅ 任务完成!")
                    print(f"   结果: {result}")
                    return True
                elif status == "failed":
                    print("❌ 任务失败")
                    return False
                elif status == "running":
                    pass  # 继续等待
                else:
                    pass  # 继续等待

            time.sleep(1)

        except Exception as e:
            print(f"  检查状态错误: {e}")
            time.sleep(1)

    print(f"❌ 任务未在 {max_attempts} 秒内完成")
    return False

def test_web_interface(url="http://localhost:8501"):
    """测试网页界面"""
    print_step(4, "测试网页界面")

    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print("✅ 网页界面可访问")

            # 检查是否是Streamlit页面
            if "streamlit" in response.text.lower():
                print("✅ 检测到Streamlit界面")
                return True
            else:
                print("⚠️  不是Streamlit界面，但可访问")
                return True
        else:
            print(f"❌ 网页界面不可访问: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 访问网页界面错误: {e}")
        print("   请确保网页界面正在运行: streamlit run web_interface.py")
        return False

def test_node_registration(url="http://localhost:8000"):
    """测试节点注册"""
    print_step(5, "测试节点注册")

    try:
        response = requests.get(f"{url}/nodes", timeout=5)
        if response.status_code == 200:
            data = response.json()
            nodes = data.get("nodes", [])
            total = data.get("total_nodes", 0)

            print("✅ 获取节点列表成功")
            print(f"   总节点数: {total}")
            print(f"   闲置节点: {data.get('total_idle', 0)}")

            if nodes:
                for i, node in enumerate(nodes[:3]):  # 显示前3个节点
                    print(f"   节点 {i+1}: {node.get('node_id')} - {node.get('status')}")

            return True
        else:
            print(f"❌ 获取节点列表失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 节点注册测试错误: {e}")
        return False

def run_comprehensive_test():
    """运行全面测试"""
    print("⚡ 闲置计算加速器 - 全面测试")
    print("="*60)

    # 获取测试URL
    scheduler_url = input("调度中心URL [http://localhost:8000]: ").strip()
    scheduler_url = scheduler_url if scheduler_url else "http://localhost:8000"

    web_url = input("网页界面URL [http://localhost:8501]: ").strip()
    web_url = web_url if web_url else "http://localhost:8501"

    results = []

    # 运行测试
    results.append(("调度中心连接", test_scheduler_connection(scheduler_url)))
    results.append(("闲置检测库", test_idle_sense_library()))
    results.append(("任务提交", test_task_submission(scheduler_url)))
    results.append(("网页界面", test_web_interface(web_url)))
    results.append(("节点注册", test_node_registration(scheduler_url)))

    # 显示结果
    print("\n" + "="*60)
    print("测试结果总结:")
    print("="*60)

    passed = 0
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {name:20} {status}")
        if success:
            passed += 1

    print(f"\n通过: {passed}/{len(results)}")

    if passed == len(results):
        print("\n🎉 所有测试通过！系统运行正常。")
        return 0
    else:
        print(f"\n⚠️  有 {len(results)-passed} 个测试失败，请检查相关组件。")
        return 1

if __name__ == "__main__":
    try:
        exit_code = run_comprehensive_test()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)

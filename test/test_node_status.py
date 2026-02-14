import requests
import json

# 测试节点状态
print("测试调度中心连接...")
try:
    response = requests.get('http://localhost:8000/', timeout=5)
    print(f"调度中心状态: {response.status_code}")
    print(f"版本信息: {response.json()}")
except Exception as e:
    print(f"无法连接调度中心: {e}")

# 测试节点列表
print("\n测试节点列表...")
try:
    response = requests.get('http://localhost:8000/api/nodes', timeout=5)
    print(f"节点列表状态: {response.status_code}")
    if response.status_code == 200:
        nodes_data = response.json()
        print(f"节点信息: {json.dumps(nodes_data, indent=2, ensure_ascii=False)}")
    else:
        print(f"获取节点列表失败: {response.text}")
except Exception as e:
    print(f"获取节点列表异常: {e}")

# 测试系统统计
print("\n测试系统统计...")
try:
    response = requests.get('http://localhost:8000/stats', timeout=5)
    print(f"系统统计状态: {response.status_code}")
    if response.status_code == 200:
        stats_data = response.json()
        print(f"统计信息: {json.dumps(stats_data, indent=2, ensure_ascii=False)[:1000]}...")
    else:
        print(f"获取统计信息失败: {response.text}")
except Exception as e:
    print(f"获取统计信息异常: {e}")

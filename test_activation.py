import requests
import time
import json

print("Testing local node activation...")

# 1. 激活本地节点
print("\n1. Activating local node...")
try:
    activation_payload = {
        "cpu_limit": 1.0,
        "memory_limit": 512,
        "storage_limit": 1024
    }
    response = requests.post('http://localhost:8000/api/nodes/activate-local', json=activation_payload, timeout=10)
    print(f"Activation Status: {response.status_code}")
    
    if response.status_code == 200:
        activation_result = response.json()
        print(f"Activation Result: {json.dumps(activation_result, indent=2)}")
        
        if activation_result.get("success"):
            node_id = activation_result["node_id"]
            print(f"Local node activated successfully with ID: {node_id}")
            
            # 2. 检查节点列表
            print("\n2. Checking node list...")
            nodes_response = requests.get('http://localhost:8000/api/nodes', timeout=10)
            print(f"Nodes Status: {nodes_response.status_code}")
            
            if nodes_response.status_code == 200:
                nodes_data = nodes_response.json()
                print(f"Available Nodes: {json.dumps(nodes_data, indent=2)}")
                
                # 3. 提交一个简单的测试任务
                print("\n3. Submitting test task...")
                task_payload = {
                    "code": "print('Hello from idle computer!'); result = 21 * 2; print(f'Result: {result}')",
                    "timeout": 30,
                    "resources": {"cpu": 0.5, "memory": 128}
                }
                task_response = requests.post('http://localhost:8000/submit', json=task_payload, timeout=10)
                print(f"Task Submission Status: {task_response.status_code}")
                
                if task_response.status_code == 200:
                    task_result = task_response.json()
                    print(f"Task Submitted: {json.dumps(task_result, indent=2)}")
                    
                    task_id = task_result.get("task_id")
                    if task_id:
                        # 4. 等待一小段时间，然后检查任务状态
                        print(f"\n4. Waiting for task execution (task_id: {task_id})...")
                        time.sleep(5)
                        
                        status_response = requests.get(f'http://localhost:8000/status/{task_id}', timeout=10)
                        print(f"Task Status Check: {status_response.status_code}")
                        
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            print(f"Task Status: {json.dumps(status_data, indent=2)}")
                        else:
                            print(f"Failed to get task status: {status_response.text}")
                else:
                    print(f"Failed to submit task: {task_response.text}")
            else:
                print(f"Failed to get nodes: {nodes_response.text}")
        else:
            print(f"Node activation failed: {activation_result}")
    else:
        print(f"Node activation request failed: {response.text}")
        
except requests.exceptions.ConnectionError:
    print("Could not connect to scheduler. Is it running on http://localhost:8000?")
except Exception as e:
    print(f"An error occurred: {e}")

print("\nTest completed.")
import requests
import json
import time

print("Checking node status...")
print("Attempting to connect to: http://localhost:8000/api/nodes")

try:
    response = requests.get('http://localhost:8000/api/nodes', timeout=10)
    print("Status Code:", response.status_code)
    print("Full Response Text:", repr(response.text))  # 使用repr显示原始内容
    
    if response.status_code == 200:
        try:
            data = response.json()
            print("\nParsed JSON Data:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except ValueError as e:
            print(f"Could not parse JSON: {e}")
            print("Raw response:", response.text)
    else:
        print(f"Error: HTTP {response.status_code}")
        
except requests.exceptions.ConnectionError:
    print("Connection Error: Could not connect to the server. Is the scheduler running?")
except requests.exceptions.Timeout:
    print("Timeout Error: Request timed out. The server might be busy or not responding.")
except Exception as e:
    print(f"Exception occurred: {type(e).__name__}: {e}")
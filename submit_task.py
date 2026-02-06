# 这是实际要创建的文件
import requests

def submit_example_task():
    # 这里是实际可运行的代码
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
    
    print(f"提交结果: {response.json()}")

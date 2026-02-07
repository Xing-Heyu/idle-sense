# c:\idle-sense\config\settings.py
import
 os
from pathlib import
 Path

# 基础配置
BASE_DIR = Path(__file__).parent.
parent
LOG_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

# 服务器配置
HOST = "0.0.0.0"
PORT = 8000
DEBUG = True

# 用户配额配置
DEFAULT_QUOTA = {
    "daily_tasks_limit": 100,
    "concurrent_tasks_limit": 5,
    "cpu_quota": 10.0,
    "memory_quota": 4096
}

# 创建必要目录
for directory in [LOG_DIR, DATA_DIR]:
    directory.mkdir(exist_ok=True)

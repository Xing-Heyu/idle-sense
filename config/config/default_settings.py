"""
config/default_settings.py
默认配置常量
"""

import os
from pathlib import Path

# 项目路径
PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"

# 确保目录存在
for directory in [LOG_DIR, DATA_DIR]:
    directory.mkdir(exist_ok=True)

# ==================== 调度中心默认配置 ====================
class SchedulerDefaults:
    """调度中心默认配置"""
    HOST = "0.0.0.0"
    PORT = 8000
    LOG_LEVEL = "INFO"
    LOG_FILE = str(LOG_DIR / "scheduler.log")
    
    # 任务队列
    MAX_QUEUE_SIZE = 1000
    RESULT_TTL = 3600  # 1小时
    CLEANUP_INTERVAL = 60
    
    # 公平调度
    SCHEDULING_POLICY = "fair_priority"
    FAIR_PRIORITY_WEIGHTS = {
        "wait_time": 0.6,
        "contribution": 0.3,
        "newcomer": 0.1
    }
    CONTRIBUTION_CAP = 10.0
    NEWCOMER_THRESHOLD = 10
    NEWCOMER_BASE_BONUS = 20
    STARVATION_THRESHOLD = 300  # 5分钟
    COOLDOWN_PERIOD = 1800  # 30分钟
    
    # 节点管理
    HEARTBEAT_INTERVAL = 30
    TIMEOUT_THRESHOLD = 90
    MAX_NODES = 100

# ==================== 节点客户端默认配置 ====================
class NodeDefaults:
    """节点客户端默认配置"""
    # 调度中心连接
    SCHEDULER_URL = "http://localhost:8000"
    NODE_NAME = os.environ.get("HOSTNAME", "unknown-node")
    
    # 闲置检测
    CHECK_INTERVAL = 30
    IDLE_THRESHOLD = 300  # 5分钟
    CPU_THRESHOLD = 30.0
    MEMORY_THRESHOLD = 70.0
    DISK_THRESHOLD = 85.0
    
    # 安全限制
    MAX_TASK_TIME = 300  # 5分钟
    MAX_MEMORY_MB = 1024  # 1GB
    MAX_DISK_MB = 100
    NETWORK_ACCESS = False
    AUTO_CLEANUP = True
    
    # 资源限制
    MAX_CPU_CORES = 2.0
    MAX_MEMORY_MB = 4096  # 4GB
    MAX_DISK_MB = 1024  # 1GB
    RESERVE_CPU = 0.5
    RESERVE_MEMORY_MB = 1024  # 1GB
    
    # 心跳
    HEARTBEAT_INTERVAL = 30
    
    # 日志
    LOG_FILE = str(LOG_DIR / "node.log")
    
    # 允许的安全模块（当网络访问禁用时）
    ALLOWED_MODULES = [
        "math", "random", "datetime", "time",
        "collections", "itertools", "functools",
        "json", "re", "statistics", "decimal",
        "fractions", "hashlib", "secrets",
        "string", "typing", "uuid"
    ]

# ==================== 网页界面默认配置 ====================
class WebDefaults:
    """网页界面默认配置"""
    # Streamlit
    STREAMLIT_PORT = 8501
    STREAMLIT_HOST = "0.0.0.0"
    THEME = "dark"
    AUTO_REFRESH = True
    REFRESH_INTERVAL = 10
    MAX_HISTORY = 50
    
    # 传统Web（备用）
    TRADITIONAL_PORT = 8080

# ==================== 监控默认配置 ====================
class MonitoringDefaults:
    """监控默认配置"""
    METRICS_PORT = 9090
    HEALTH_CHECK_ENDPOINT = "/health"
    STATS_RETENTION_DAYS = 7

# ==================== 路径配置 ====================
class PathDefaults:
    """路径默认配置"""
    # 任务临时目录
    TASK_TEMP_DIR = str(PROJECT_ROOT / "tmp" / "tasks")
    
    # 结果存储
    RESULTS_DIR = str(DATA_DIR / "results")
    
    # 配置文件
    CONFIG_FILE = str(CONFIG_DIR / "config.yaml")
    
    # PID文件（用于进程管理）
    PID_DIR = str(PROJECT_ROOT / "tmp" / "pids")

# ==================== 安全默认配置 ====================
class SecurityDefaults:
    """安全默认配置"""
    # 沙箱配置
    SANDBOX_TYPE = "tempdir"  # tempdir, docker, none
    TEMP_DIR = "/tmp/idle_tasks"
    
    # 进程限制
    ISOLATE_PROCESS = True
    DROP_PRIVILEGES = True
    
    # 网络限制
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
    
    # 输入验证
    MAX_CODE_SIZE = 10000  # 最大代码大小（字符）
    MAX_INPUT_SIZE = 1024  # 最大输入数据大小（KB）

# ==================== 导出所有默认配置 ====================
SCHEDULER = SchedulerDefaults()
NODE = NodeDefaults()
WEB = WebDefaults()
MONITORING = MonitoringDefaults()
PATHS = PathDefaults()
SECURITY = SecurityDefaults()

# 方便导入的别名
DEFAULTS = {
    "scheduler": SCHEDULER,
    "node": NODE,
    "web": WEB,
    "monitoring": MONITORING,
    "paths": PATHS,
    "security": SECURITY
}

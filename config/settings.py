"""
配置管理模块 - 基于 Pydantic Settings

使用 Pydantic Settings 进行类型安全的配置管理，支持：
- 环境变量注入
- YAML 配置文件
- 默认值和验证
- 多环境配置

安装依赖：
    pip install pydantic-settings pyyaml

使用示例：
    from config.settings import settings

    # 获取配置
    scheduler_url = settings.SCHEDULER_URL
    refresh_interval = settings.REFRESH_INTERVAL

    # 运行时修改（可选）
    settings.SCHEDULER_URL = "http://new-host:8000"
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from pydantic import Field, field_validator
    from pydantic_settings import BaseSettings, SettingsConfigDict
    PYDANTIC_V2 = True
except ImportError:
    from pydantic import BaseSettings, Field, validator
    PYDANTIC_V2 = False


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


class SchedulerSettings(BaseSettings):
    """调度器配置"""

    model_config = SettingsConfigDict(
        env_prefix="SCHEDULER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    ) if PYDANTIC_V2 else {}

    URL: str = Field(
        default="http://localhost:8000",
        description="调度器URL地址"
    )
    API_TIMEOUT: int = Field(
        default=10,
        ge=1,
        le=300,
        description="API调用超时时间（秒）"
    )
    HEALTH_CHECK_TIMEOUT: int = Field(
        default=3,
        ge=1,
        le=30,
        description="健康检查超时时间（秒）"
    )
    MAX_RETRIES: int = Field(
        default=3,
        ge=0,
        le=10,
        description="最大重试次数"
    )
    RETRY_DELAY: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="重试延迟时间（秒）"
    )

    if PYDANTIC_V2:
        @field_validator("URL")
        @classmethod
        def validate_url(cls, v: str) -> str:
            if not v.startswith(("http://", "https://")):
                raise ValueError("URL must start with http:// or https://")
            return v.rstrip("/")
    else:
        @validator("URL")
        def validate_url(cls, v: str) -> str:
            if not v.startswith(("http://", "https://")):
                raise ValueError("URL must start with http:// or https://")
            return v.rstrip("/")


class ResourceSettings(BaseSettings):
    """资源配置"""

    model_config = SettingsConfigDict(
        env_prefix="RESOURCE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    ) if PYDANTIC_V2 else {}

    DEFAULT_CPU_SHARE: float = Field(
        default=4.0,
        ge=0.5,
        le=32.0,
        description="默认CPU共享核心数"
    )
    DEFAULT_MEMORY_SHARE: int = Field(
        default=8192,
        ge=512,
        le=65536,
        description="默认内存共享（MB）"
    )
    MIN_CPU_SHARE: float = Field(
        default=0.5,
        description="最小CPU共享"
    )
    MAX_CPU_SHARE: float = Field(
        default=16.0,
        description="最大CPU共享"
    )
    MIN_MEMORY_SHARE: int = Field(
        default=512,
        description="最小内存共享（MB）"
    )
    MAX_MEMORY_SHARE: int = Field(
        default=32768,
        description="最大内存共享（MB）"
    )
    DEFAULT_STORAGE_SHARE: int = Field(
        default=10240,
        ge=1024,
        le=102400,
        description="默认存储共享（MB）"
    )


class WebUISettings(BaseSettings):
    """Web UI 配置"""

    model_config = SettingsConfigDict(
        env_prefix="WEB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    ) if PYDANTIC_V2 else {}

    PAGE_TITLE: str = Field(
        default="闲置计算加速器",
        description="页面标题"
    )
    PAGE_ICON: str = Field(
        default="⚡",
        description="页面图标"
    )
    LAYOUT: str = Field(
        default="wide",
        description="页面布局"
    )
    INITIAL_SIDEBAR_STATE: str = Field(
        default="expanded",
        description="侧边栏初始状态"
    )
    AUTO_REFRESH: bool = Field(
        default=False,
        description="自动刷新"
    )
    REFRESH_INTERVAL: int = Field(
        default=30,
        ge=5,
        le=300,
        description="刷新间隔（秒）"
    )
    MAX_HISTORY: int = Field(
        default=50,
        ge=10,
        le=200,
        description="最大历史记录数"
    )
    DEBUG_MODE: bool = Field(
        default=False,
        description="调试模式"
    )


class StorageSettings(BaseSettings):
    """存储路径配置"""

    model_config = SettingsConfigDict(
        env_prefix="STORAGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    ) if PYDANTIC_V2 else {}

    BACKEND: str = Field(
        default="memory",
        description="存储后端类型: memory, sqlite, redis"
    )
    SQLITE_DB_PATH: str = Field(
        default=str(PROJECT_ROOT / "data" / "idle_sense.db"),
        description="SQLite数据库路径"
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis连接URL"
    )
    REDIS_KEY_PREFIX: str = Field(
        default="idle_sense:",
        description="Redis键前缀"
    )
    DATA_TTL: int = Field(
        default=86400,
        ge=3600,
        le=604800,
        description="数据TTL（秒）"
    )
    USERS_DIR: str = Field(
        default=str(PROJECT_ROOT / "local_users"),
        description="用户数据目录"
    )
    NODE_DATA_DIR: str = Field(
        default=str(PROJECT_ROOT / "node_data"),
        description="节点数据目录"
    )
    LOG_DIR: str = Field(
        default=str(PROJECT_ROOT / "logs"),
        description="日志目录"
    )
    TEMP_DIR: str = Field(
        default=str(PROJECT_ROOT / "tmp"),
        description="临时文件目录"
    )

    def ensure_directories(self) -> None:
        """确保所有目录存在"""
        for dir_path in [self.USERS_DIR, self.NODE_DATA_DIR, self.LOG_DIR, self.TEMP_DIR]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)


class DistributedTaskSettings(BaseSettings):
    """分布式任务配置"""

    model_config = SettingsConfigDict(
        env_prefix="DISTRIBUTED_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    ) if PYDANTIC_V2 else {}

    DEFAULT_CHUNK_SIZE: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="默认分片大小"
    )
    DEFAULT_MAX_PARALLEL_CHUNKS: int = Field(
        default=5,
        ge=1,
        le=50,
        description="默认最大并行分片数"
    )
    TASK_TIMEOUT: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="任务超时时间（秒）"
    )
    RESULT_TTL: int = Field(
        default=86400,
        ge=3600,
        le=604800,
        description="结果保留时间（秒）"
    )


class SecuritySettings(BaseSettings):
    """安全配置"""

    model_config = SettingsConfigDict(
        env_prefix="SECURITY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    ) if PYDANTIC_V2 else {}

    MAX_CODE_SIZE: int = Field(
        default=10000,
        ge=100,
        le=100000,
        description="最大代码大小（字符）"
    )
    MAX_INPUT_SIZE: int = Field(
        default=1024,
        ge=1,
        le=10240,
        description="最大输入数据大小（KB）"
    )
    SANDBOX_ENABLED: bool = Field(
        default=True,
        description="是否启用沙箱"
    )
    NETWORK_ACCESS: bool = Field(
        default=False,
        description="是否允许网络访问"
    )
    ALLOWED_MODULES: list[str] = Field(
        default=[
            "math", "random", "datetime", "time",
            "collections", "itertools", "functools",
            "json", "re", "statistics", "decimal",
            "fractions", "hashlib", "secrets",
            "string", "typing", "uuid"
        ],
        description="允许的安全模块列表"
    )


class TokenEconomySettings(BaseSettings):
    """代币经济配置"""

    model_config = SettingsConfigDict(
        env_prefix="TOKEN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    ) if PYDANTIC_V2 else {}

    INITIAL_BALANCE: float = Field(
        default=1000.0,
        ge=0,
        description="新用户初始余额"
    )
    UPTIME_REWARD_INTERVAL: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="在线时间奖励间隔（秒）"
    )
    BASE_REWARD_PER_MINUTE: float = Field(
        default=1.0,
        ge=0.1,
        description="每分钟基础奖励"
    )


class Settings(BaseSettings):
    """
    主配置类 - 整合所有配置

    支持环境变量覆盖，优先级：
    1. 环境变量（最高优先级）
    2. .env 文件
    3. 默认值（最低优先级）
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    ) if PYDANTIC_V2 else {}

    # 应用信息
    APP_NAME: str = Field(default="闲置计算加速器", description="应用名称")
    APP_VERSION: str = Field(default="2.0.0", description="应用版本")
    DEBUG: bool = Field(default=False, description="调试模式")

    # 子配置
    SCHEDULER: SchedulerSettings = Field(default_factory=SchedulerSettings)
    RESOURCE: ResourceSettings = Field(default_factory=ResourceSettings)
    WEB: WebUISettings = Field(default_factory=WebUISettings)
    STORAGE: StorageSettings = Field(default_factory=StorageSettings)
    DISTRIBUTED: DistributedTaskSettings = Field(default_factory=DistributedTaskSettings)
    SECURITY: SecuritySettings = Field(default_factory=SecuritySettings)
    TOKEN: TokenEconomySettings = Field(default_factory=TokenEconomySettings)

    # 兼容旧代码的快捷属性
    @property
    def PATH(self) -> StorageSettings:
        """路径配置（兼容旧代码）"""
        return self.STORAGE
    @property
    def SCHEDULER_URL(self) -> str:
        """调度器URL（兼容旧代码）"""
        return self.SCHEDULER.URL

    @property
    def REFRESH_INTERVAL(self) -> int:
        """刷新间隔（兼容旧代码）"""
        return self.WEB.REFRESH_INTERVAL

    @property
    def API_TIMEOUT(self) -> int:
        """API超时（兼容旧代码）"""
        return self.SCHEDULER.API_TIMEOUT

    def ensure_directories(self) -> None:
        """确保所有必要目录存在"""
        self.STORAGE.ensure_directories()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "APP_NAME": self.APP_NAME,
            "APP_VERSION": self.APP_VERSION,
            "DEBUG": self.DEBUG,
            "SCHEDULER": self.SCHEDULER.model_dump() if PYDANTIC_V2 else self.SCHEDULER.dict(),
            "RESOURCE": self.RESOURCE.model_dump() if PYDANTIC_V2 else self.RESOURCE.dict(),
            "WEB": self.WEB.model_dump() if PYDANTIC_V2 else self.WEB.dict(),
            "STORAGE": self.STORAGE.model_dump() if PYDANTIC_V2 else self.STORAGE.dict(),
            "DISTRIBUTED": self.DISTRIBUTED.model_dump() if PYDANTIC_V2 else self.DISTRIBUTED.dict(),
            "SECURITY": self.SECURITY.model_dump() if PYDANTIC_V2 else self.SECURITY.dict(),
            "TOKEN": self.TOKEN.model_dump() if PYDANTIC_V2 else self.TOKEN.dict(),
        }


@lru_cache
def get_settings() -> Settings:
    """
    获取配置实例（单例模式）

    使用 lru_cache 确保配置只加载一次
    """
    settings = Settings()
    settings.ensure_directories()
    return settings


# 全局配置实例
settings = get_settings()


# 导出
__all__ = [
    "Settings",
    "SchedulerSettings",
    "ResourceSettings",
    "WebUISettings",
    "StorageSettings",
    "DistributedTaskSettings",
    "SecuritySettings",
    "TokenEconomySettings",
    "settings",
    "get_settings",
]

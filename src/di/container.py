"""
依赖注入容器

使用 dependency-injector 库实现依赖注入，支持：
- 单例模式
- 工厂模式
- 配置注入
- 服务注入
- 可配置存储后端

安装依赖：
    pip install dependency-injector

使用示例：
    from src.di import Container, container

    # 初始化容器
    container = Container()
    container.wire(modules=[__name__])

    # 使用依赖注入
    from dependency_injector.wiring import inject, Provide

    @inject
    def my_function(client = Provide[Container.scheduler_client]):
        return client.check_health()
"""


try:
    from dependency_injector import containers, providers
    from dependency_injector.wiring import Provide, inject
    DEPENDENCY_INJECTOR_AVAILABLE = True
except ImportError:
    DEPENDENCY_INJECTOR_AVAILABLE = False
    containers = None
    providers = None
    inject = None
    Provide = None

from config.settings import get_settings
from legacy.token_economy import TokenEconomy
from src.core.services import IdleDetectionService, PermissionService, TokenEconomyService
from src.core.use_cases.auth import LoginUseCase, RegisterUseCase
from src.core.use_cases.system import CreateFoldersUseCase, FolderService
from src.infrastructure.audit import AuditLogger
from src.infrastructure.external import DistributedTaskClient, SchedulerClient
from src.infrastructure.repositories import (
    FileUserRepository,
    InMemoryNodeRepository,
    InMemoryTaskRepository,
    RedisNodeRepository,
    RedisTaskRepository,
    SQLiteNodeRepository,
    SQLiteTaskRepository,
)
from src.infrastructure.sandbox import IsolationLevel, SandboxConfig, SandboxFactory
from src.infrastructure.scheduler import AdvancedScheduler, SchedulingPolicy, SimpleScheduler
from src.infrastructure.utils import MemoryCache


def create_node_repository(backend: str, config):
    """创建节点仓储实例"""
    if backend == "sqlite":
        return SQLiteNodeRepository(db_path=config.SQLITE_DB_PATH)
    elif backend == "redis":
        return RedisNodeRepository(
            redis_url=config.REDIS_URL,
            key_prefix=config.REDIS_KEY_PREFIX + "node:",
            ttl=config.DATA_TTL
        )
    else:
        return InMemoryNodeRepository()


def create_task_repository(backend: str, config):
    """创建任务仓储实例"""
    if backend == "sqlite":
        return SQLiteTaskRepository(db_path=config.SQLITE_DB_PATH)
    elif backend == "redis":
        return RedisTaskRepository(
            redis_url=config.REDIS_URL,
            key_prefix=config.REDIS_KEY_PREFIX + "task:",
            ttl=config.DATA_TTL
        )
    else:
        return InMemoryTaskRepository()


class Container(containers.DeclarativeContainer if DEPENDENCY_INJECTOR_AVAILABLE else object):
    """
    依赖注入容器

    管理所有依赖的生命周期和注入

    Examples:
        >>> container = Container()
        >>> container.wire(modules=[__name__])
        >>>
        >>> @inject
        ... def my_function(client = Provide[Container.scheduler_client]):
        ...     return client.check_health()
    """

    if DEPENDENCY_INJECTOR_AVAILABLE:
        config = providers.Singleton(
            lambda: get_settings()
        )

        cache = providers.Singleton(
            MemoryCache,
            max_size=1000,
            default_ttl=300
        )

        scheduler_client = providers.Singleton(
            SchedulerClient,
            base_url=config.provided.SCHEDULER.URL,
            timeout=config.provided.SCHEDULER.API_TIMEOUT,
            health_check_timeout=config.provided.SCHEDULER.HEALTH_CHECK_TIMEOUT,
            max_retries=config.provided.SCHEDULER.MAX_RETRIES
        )

        token_economy = providers.Singleton(
            TokenEconomy
        )

        token_economy_service = providers.Singleton(
            TokenEconomyService,
            token_economy=token_economy
        )

        idle_detection_service = providers.Singleton(
            IdleDetectionService,
            idle_threshold_sec=config.provided.TOKEN.UPTIME_REWARD_INTERVAL,
            cpu_threshold=15.0,
            memory_threshold=70.0
        )

        simple_scheduler = providers.Singleton(
            SimpleScheduler
        )

        advanced_scheduler = providers.Singleton(
            AdvancedScheduler,
            policy=SchedulingPolicy.DRF
        )

        sandbox_factory = providers.Singleton(
            SandboxFactory
        )

        sandbox_config = providers.Singleton(
            SandboxConfig,
            timeout=300,
            memory_limit=512,
            cpu_limit=1.0,
            isolation_level=IsolationLevel.BASIC
        )

        node_repository = providers.Singleton(
            create_node_repository,
            backend=config.provided.STORAGE.BACKEND,
            config=config.provided.STORAGE
        )

        task_repository = providers.Singleton(
            create_task_repository,
            backend=config.provided.STORAGE.BACKEND,
            config=config.provided.STORAGE
        )

        user_repository = providers.Singleton(
            FileUserRepository,
            users_dir=config.provided.STORAGE.USERS_DIR
        )

        audit_logger = providers.Singleton(
            AuditLogger,
            db_path="audit.db"
        )

        register_use_case = providers.Factory(
            RegisterUseCase,
            user_repository=user_repository,
            audit_logger=audit_logger
        )

        login_use_case = providers.Factory(
            LoginUseCase,
            user_repository=user_repository
        )

        permission_service = providers.Singleton(PermissionService)

        folder_service = providers.Singleton(FolderService)

        create_folders_use_case = providers.Factory(
            CreateFoldersUseCase,
            folder_service=folder_service
        )

        try:
            from legacy.distributed_task import DistributedTaskManager
            distributed_task_manager = providers.Singleton(
                DistributedTaskManager,
                scheduler_url=config.provided.SCHEDULER.URL
            )
            distributed_task_client = providers.Singleton(
                DistributedTaskClient,
                distributed_task_manager=distributed_task_manager
            )
        except ImportError:
            distributed_task_client = providers.Singleton(
                DistributedTaskClient,
                distributed_task_manager=None
            )
    else:
        def __init__(self):
            self._config = get_settings()
            self._cache = MemoryCache(max_size=1000, default_ttl=300)
            self._scheduler_client = SchedulerClient(
                base_url=self._config.SCHEDULER.URL,
                timeout=self._config.SCHEDULER.API_TIMEOUT,
                health_check_timeout=self._config.SCHEDULER.HEALTH_CHECK_TIMEOUT,
                max_retries=self._config.SCHEDULER.MAX_RETRIES
            )
            self._token_economy = TokenEconomy()
            self._token_economy_service = TokenEconomyService(self._token_economy)
            self._idle_detection_service = IdleDetectionService(
                idle_threshold_sec=self._config.TOKEN.UPTIME_REWARD_INTERVAL
            )
            self._simple_scheduler = SimpleScheduler()
            self._advanced_scheduler = AdvancedScheduler(policy=SchedulingPolicy.DRF)
            self._sandbox_factory = SandboxFactory()
            self._sandbox_config = SandboxConfig(
                timeout=300,
                memory_limit=512,
                cpu_limit=1.0,
                isolation_level=IsolationLevel.BASIC
            )
            self._node_repository = create_node_repository(
                self._config.STORAGE.BACKEND,
                self._config.STORAGE
            )
            self._task_repository = create_task_repository(
                self._config.STORAGE.BACKEND,
                self._config.STORAGE
            )
            self._user_repository = FileUserRepository(
                users_dir=self._config.STORAGE.USERS_DIR
            )
            self._audit_logger = AuditLogger(db_path="audit.db")
            self._register_use_case = RegisterUseCase(
                self._user_repository,
                self._audit_logger
            )
            self._login_use_case = LoginUseCase(self._user_repository)
            self._permission_service = PermissionService()
            self._folder_service = FolderService()
            self._create_folders_use_case = CreateFoldersUseCase(self._folder_service)
            try:
                from legacy.distributed_task import DistributedTaskManager
                manager = DistributedTaskManager(self._config.SCHEDULER.URL)
                self._distributed_task_client = DistributedTaskClient(manager)
            except ImportError:
                self._distributed_task_client = DistributedTaskClient(None)

        @property
        def config(self):
            return self._config

        @property
        def cache(self):
            return self._cache

        @property
        def scheduler_client(self):
            return self._scheduler_client

        @property
        def token_economy(self):
            return self._token_economy

        @property
        def token_economy_service(self):
            return self._token_economy_service

        @property
        def idle_detection_service(self):
            return self._idle_detection_service

        @property
        def simple_scheduler(self):
            return self._simple_scheduler

        @property
        def advanced_scheduler(self):
            return self._advanced_scheduler

        @property
        def sandbox_factory(self):
            return self._sandbox_factory

        @property
        def sandbox_config(self):
            return self._sandbox_config

        @property
        def node_repository(self):
            return self._node_repository

        @property
        def task_repository(self):
            return self._task_repository

        @property
        def user_repository(self):
            return self._user_repository

        @property
        def audit_logger(self):
            return self._audit_logger

        @property
        def register_use_case(self):
            return self._register_use_case

        @property
        def login_use_case(self):
            return self._login_use_case

        @property
        def permission_service(self):
            return self._permission_service

        @property
        def folder_service(self):
            return self._folder_service

        @property
        def create_folders_use_case(self):
            return self._create_folders_use_case

        @property
        def distributed_task_client(self):
            return self._distributed_task_client

    def wire(self, modules: list) -> None:
        """
        连接模块进行依赖注入

        Args:
            modules: 需要注入的模块列表
        """
        if DEPENDENCY_INJECTOR_AVAILABLE:
            super().wire(modules=modules)

    def unwire(self) -> None:
        """断开模块连接"""
        if DEPENDENCY_INJECTOR_AVAILABLE:
            super().unwire()


container = Container()


def simple_inject(func):
    """
    简化的注入装饰器

    当 dependency-injector 不可用时使用
    """
    if DEPENDENCY_INJECTOR_AVAILABLE:
        return inject(func)
    else:
        return func


__all__ = [
    "Container",
    "container",
    "simple_inject",
    "DEPENDENCY_INJECTOR_AVAILABLE",
    "create_node_repository",
    "create_task_repository",
]

if DEPENDENCY_INJECTOR_AVAILABLE:
    __all__.extend(["inject", "Provide"])

"""
Dependency Injection Framework.

A lightweight dependency injection container inspired by:
- Python dependency-injector
- Spring IoC Container
- FastAPI Depends

Usage:
    container = Container()

    # Register dependencies
    container.register_singleton(Database, PostgresDatabase)
    container.register_transient(UserService, UserServiceImpl)

    # Resolve dependencies
    db = container.resolve(Database)
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Optional,
    TypeVar,
    Union,
    get_type_hints,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Scope(str, Enum):
    """Dependency scope enumeration."""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


@dataclass
class DependencyDescriptor:
    """Descriptor for a registered dependency."""
    interface: type
    implementation: type
    scope: Scope = Scope.TRANSIENT
    factory: Optional[Callable] = None
    instance: Optional[Any] = None
    dependencies: dict[str, type] = field(default_factory=dict)


class Container:
    """
    Dependency injection container.

    Features:
    - Singleton, transient, and scoped lifecycles
    - Automatic dependency resolution
    - Factory function support
    - Circular dependency detection
    """

    def __init__(self):
        self._registrations: dict[type, DependencyDescriptor] = {}
        self._singletons: dict[type, Any] = {}
        self._scoped_instances: dict[type, Any] = {}
        self._resolving: set[type] = set()

    def register_singleton(
        self,
        interface: type[T],
        implementation: Optional[type[T]] = None,
        factory: Optional[Callable[[], T]] = None
    ) -> None:
        """Register a singleton dependency."""
        self._register(
            interface=interface,
            implementation=implementation or interface,
            scope=Scope.SINGLETON,
            factory=factory
        )

    def register_transient(
        self,
        interface: type[T],
        implementation: Optional[type[T]] = None,
        factory: Optional[Callable[[], T]] = None
    ) -> None:
        """Register a transient dependency."""
        self._register(
            interface=interface,
            implementation=implementation or interface,
            scope=Scope.TRANSIENT,
            factory=factory
        )

    def register_scoped(
        self,
        interface: type[T],
        implementation: Optional[type[T]] = None,
        factory: Optional[Callable[[], T]] = None
    ) -> None:
        """Register a scoped dependency."""
        self._register(
            interface=interface,
            implementation=implementation or interface,
            scope=Scope.SCOPED,
            factory=factory
        )

    def register_instance(
        self,
        interface: type[T],
        instance: T
    ) -> None:
        """Register an existing instance as a singleton."""
        self._singletons[interface] = instance
        self._registrations[interface] = DependencyDescriptor(
            interface=interface,
            implementation=type(instance),
            scope=Scope.SINGLETON,
            instance=instance
        )

    def _register(
        self,
        interface: type,
        implementation: type,
        scope: Scope,
        factory: Optional[Callable] = None
    ) -> None:
        """Internal registration method."""
        dependencies = self._analyze_dependencies(implementation)

        self._registrations[interface] = DependencyDescriptor(
            interface=interface,
            implementation=implementation,
            scope=scope,
            factory=factory,
            dependencies=dependencies
        )

        logger.debug(
            f"Registered {interface.__name__} -> {implementation.__name__} ({scope.value})"
        )

    def _analyze_dependencies(self, cls: type) -> dict[str, type]:
        """Analyze constructor dependencies."""
        dependencies = {}

        try:
            hints = get_type_hints(cls.__init__)
        except (TypeError, NameError):
            return dependencies

        for param_name, param_type in hints.items():
            if param_name == "return":
                continue

            if isinstance(param_type, type):
                dependencies[param_name] = param_type

        return dependencies

    def resolve(self, interface: type[T]) -> T:
        """
        Resolve a dependency.

        Args:
            interface: The interface type to resolve

        Returns:
            The resolved instance

        Raises:
            KeyError: If dependency not registered
            RuntimeError: If circular dependency detected
        """
        if interface not in self._registrations:
            raise KeyError(f"Dependency not registered: {interface.__name__}")

        descriptor = self._registrations[interface]

        if descriptor.scope == Scope.SINGLETON and interface in self._singletons:
            return self._singletons[interface]

        if descriptor.scope == Scope.SCOPED and interface in self._scoped_instances:
            return self._scoped_instances[interface]

        if interface in self._resolving:
            raise RuntimeError(
                f"Circular dependency detected: {interface.__name__}"
            )

        self._resolving.add(interface)

        try:
            instance = self._create_instance(descriptor)

            if descriptor.scope == Scope.SINGLETON:
                self._singletons[interface] = instance
            elif descriptor.scope == Scope.SCOPED:
                self._scoped_instances[interface] = instance

            return instance
        finally:
            self._resolving.discard(interface)

    def _create_instance(self, descriptor: DependencyDescriptor) -> Any:
        """Create an instance from a descriptor."""
        if descriptor.factory:
            return descriptor.factory()

        kwargs = {}
        for param_name, param_type in descriptor.dependencies.items():
            if param_type in self._registrations:
                kwargs[param_name] = self.resolve(param_type)

        return descriptor.implementation(**kwargs)

    def try_resolve(self, interface: type[T]) -> Optional[T]:
        """Try to resolve a dependency, returning None if not found."""
        try:
            return self.resolve(interface)
        except KeyError:
            return None

    def is_registered(self, interface: type) -> bool:
        """Check if a dependency is registered."""
        return interface in self._registrations

    def clear_scoped(self) -> None:
        """Clear all scoped instances."""
        self._scoped_instances.clear()

    def clear_all(self) -> None:
        """Clear all registrations and instances."""
        self._registrations.clear()
        self._singletons.clear()
        self._scoped_instances.clear()


class Injectable:
    """Base class for injectable services."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)


def injectable(cls: type[T] = None, *, scope: Scope = Scope.TRANSIENT) -> Union[type[T], Callable[[type[T]], type[T]]]:
    """
    Decorator to mark a class as injectable.

    Usage:
        @injectable
        class MyService:
            pass

        @injectable(scope=Scope.SINGLETON)
        class Database:
            pass
    """
    def decorator(c: type[T]) -> type[T]:
        c._injectable_scope = scope
        return c

    if cls is not None:
        return decorator(cls)
    return decorator


def inject(interface: type[T]) -> T:
    """
    Function to mark a parameter for injection.

    Usage:
        def my_function(db: Database = inject(Database)):
            pass
    """
    return interface


_global_container: Optional[Container] = None


def get_container() -> Container:
    """Get the global container instance."""
    global _global_container
    if _global_container is None:
        _global_container = Container()
    return _global_container


def configure_container(container: Container) -> None:
    """Set the global container."""
    global _global_container
    _global_container = container

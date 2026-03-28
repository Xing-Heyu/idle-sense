"""
Plugin System Architecture.

A flexible plugin system inspired by:
- Python setuptools entry points
- VS Code extensions
- WordPress plugins

Usage:
    # Define a plugin hook
    @hook("task_pre_execute")
    def my_hook(task):
        print(f"Executing task {task.id}")

    # Register a plugin
    plugin_manager.register(MyPlugin())

    # Trigger hooks
    plugin_manager.trigger("task_pre_execute", task=task)
"""
import inspect
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    """Plugin metadata."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    dependencies: list[str] = field(default_factory=list)
    enabled: bool = True
    priority: int = 100


class PluginBase(ABC):
    """Base class for plugins."""

    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """Get plugin information."""
        pass

    def on_load(self) -> None:  # noqa: B027
        """Called when plugin is loaded."""
        pass

    def on_unload(self) -> None:  # noqa: B027
        """Called when plugin is unloaded."""
        pass

    def on_enable(self) -> None:  # noqa: B027
        """Called when plugin is enabled."""
        pass

    def on_disable(self) -> None:  # noqa: B027
        """Called when plugin is disabled."""
        pass


class Hook:
    """Represents a registered hook."""

    def __init__(
        self,
        hook_name: str,
        callback: Callable,
        priority: int = 100,
        plugin_name: Optional[str] = None
    ):
        self.hook_name = hook_name
        self.callback = callback
        self.priority = priority
        self.plugin_name = plugin_name

    def __lt__(self, other: "Hook") -> bool:
        return self.priority < other.priority


class HookType:
    """Predefined hook types."""

    # Task lifecycle hooks
    TASK_SUBMIT = "task_submit"
    TASK_PRE_EXECUTE = "task_pre_execute"
    TASK_POST_EXECUTE = "task_post_execute"
    TASK_COMPLETE = "task_complete"
    TASK_FAIL = "task_fail"

    # Node lifecycle hooks
    NODE_REGISTER = "node_register"
    NODE_HEARTBEAT = "node_heartbeat"
    NODE_OFFLINE = "node_offline"

    # Scheduler hooks
    SCHEDULER_PRE_SCHEDULE = "scheduler_pre_schedule"
    SCHEDULER_POST_SCHEDULE = "scheduler_post_schedule"

    # System hooks
    SYSTEM_START = "system_start"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_ERROR = "system_error"


class PluginManager:
    """
    Central plugin manager.

    Features:
    - Plugin registration and lifecycle management
    - Hook system for extensibility
    - Plugin discovery from entry points
    - Dependency resolution
    """

    def __init__(self):
        self._plugins: dict[str, PluginBase] = {}
        self._hooks: dict[str, list[Hook]] = {}
        self._hook_registry: dict[str, Callable] = {}

    def register(self, plugin: PluginBase) -> bool:
        """Register a plugin."""
        info = plugin.info

        if info.name in self._plugins:
            logger.warning(f"Plugin already registered: {info.name}")
            return False

        if not self._check_dependencies(info.dependencies):
            logger.error(f"Plugin dependencies not met: {info.name}")
            return False

        self._plugins[info.name] = plugin
        plugin.on_load()

        if info.enabled:
            plugin.on_enable()

        logger.info(f"Registered plugin: {info.name} v{info.version}")
        return True

    def unregister(self, plugin_name: str) -> bool:
        """Unregister a plugin."""
        if plugin_name not in self._plugins:
            return False

        plugin = self._plugins[plugin_name]
        plugin.on_disable()
        plugin.on_unload()

        self._remove_plugin_hooks(plugin_name)
        del self._plugins[plugin_name]

        logger.info(f"Unregistered plugin: {plugin_name}")
        return True

    def enable(self, plugin_name: str) -> bool:
        """Enable a plugin."""
        if plugin_name not in self._plugins:
            return False

        plugin = self._plugins[plugin_name]
        plugin.info.enabled = True
        plugin.on_enable()

        logger.info(f"Enabled plugin: {plugin_name}")
        return True

    def disable(self, plugin_name: str) -> bool:
        """Disable a plugin."""
        if plugin_name not in self._plugins:
            return False

        plugin = self._plugins[plugin_name]
        plugin.info.enabled = False
        plugin.on_disable()

        logger.info(f"Disabled plugin: {plugin_name}")
        return True

    def get_plugin(self, plugin_name: str) -> Optional[PluginBase]:
        """Get a plugin by name."""
        return self._plugins.get(plugin_name)

    def list_plugins(self) -> list[PluginInfo]:
        """List all registered plugins."""
        return [p.info for p in self._plugins.values()]

    def _check_dependencies(self, dependencies: list[str]) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep in self._plugins for dep in dependencies)

    def _remove_plugin_hooks(self, plugin_name: str) -> None:
        """Remove all hooks registered by a plugin."""
        for hook_name in list(self._hooks.keys()):
            self._hooks[hook_name] = [
                h for h in self._hooks[hook_name]
                if h.plugin_name != plugin_name
            ]

    def register_hook(
        self,
        hook_name: str,
        callback: Callable,
        priority: int = 100,
        plugin_name: Optional[str] = None
    ) -> None:
        """Register a hook callback."""
        hook = Hook(
            hook_name=hook_name,
            callback=callback,
            priority=priority,
            plugin_name=plugin_name
        )

        if hook_name not in self._hooks:
            self._hooks[hook_name] = []

        self._hooks[hook_name].append(hook)
        self._hooks[hook_name].sort()

        logger.debug(f"Registered hook: {hook_name} (priority: {priority})")

    def unregister_hook(self, hook_name: str, callback: Callable) -> bool:
        """Unregister a hook callback."""
        if hook_name not in self._hooks:
            return False

        original_len = len(self._hooks[hook_name])
        self._hooks[hook_name] = [
            h for h in self._hooks[hook_name]
            if h.callback != callback
        ]

        return len(self._hooks[hook_name]) < original_len

    def trigger(
        self,
        hook_name: str,
        *args,
        **kwargs
    ) -> list[Any]:
        """
        Trigger a hook.

        Args:
            hook_name: Name of the hook to trigger
            *args: Positional arguments to pass to callbacks
            **kwargs: Keyword arguments to pass to callbacks

        Returns:
            List of results from all callbacks
        """
        if hook_name not in self._hooks:
            return []

        results = []

        for hook in self._hooks[hook_name]:
            try:
                result = hook.callback(*args, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(
                    f"Hook callback error ({hook_name}): {e}"
                )

        return results

    async def trigger_async(
        self,
        hook_name: str,
        *args,
        **kwargs
    ) -> list[Any]:
        """Trigger a hook asynchronously."""
        if hook_name not in self._hooks:
            return []

        import asyncio

        results = []

        for hook in self._hooks[hook_name]:
            try:
                if asyncio.iscoroutinefunction(hook.callback):
                    result = await hook.callback(*args, **kwargs)
                else:
                    result = hook.callback(*args, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(
                    f"Async hook callback error ({hook_name}): {e}"
                )

        return results

    def discover_plugins(self, entry_point_group: str = "idle_accelerator.plugins") -> int:
        """
        Discover plugins from entry points.

        Returns:
            Number of plugins discovered
        """
        try:
            import importlib.metadata as metadata
        except ImportError:
            import importlib_metadata as metadata

        discovered = 0

        try:
            entry_points = metadata.entry_points()

            if hasattr(entry_points, 'select'):
                eps = entry_points.select(group=entry_point_group)
            else:
                eps = entry_points.get(entry_point_group, [])

            for ep in eps:
                try:
                    plugin_class = ep.load()

                    if inspect.isclass(plugin_class) and issubclass(plugin_class, PluginBase):
                        plugin = plugin_class()
                        if self.register(plugin):
                            discovered += 1
                except Exception as e:
                    logger.error(f"Failed to load plugin {ep.name}: {e}")

        except Exception as e:
            logger.error(f"Plugin discovery failed: {e}")

        return discovered


def hook(
    hook_name: str,
    priority: int = 100,
    plugin_name: Optional[str] = None
) -> Callable:
    """
    Decorator to register a hook.

    Usage:
        @hook("task_pre_execute", priority=50)
        def my_hook(task):
            print(f"Executing: {task.id}")
    """
    def decorator(func: Callable) -> Callable:
        get_plugin_manager().register_hook(
            hook_name=hook_name,
            callback=func,
            priority=priority,
            plugin_name=plugin_name
        )
        return func
    return decorator


_global_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager."""
    global _global_plugin_manager
    if _global_plugin_manager is None:
        _global_plugin_manager = PluginManager()
    return _global_plugin_manager

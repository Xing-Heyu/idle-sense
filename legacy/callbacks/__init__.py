"""
Task Callback System.

This module provides callback mechanisms for task lifecycle events,
inspired by Celery's callback system.

Usage:
    # Success callback
    @task_callback.on_success
    def handle_success(result, task_id):
        print(f"Task {task_id} succeeded: {result}")

    # Failure callback
    @task_callback.on_failure
    def handle_failure(error, task_id):
        print(f"Task {task_id} failed: {error}")
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class CallbackContext:
    """Context passed to callback functions."""
    task_id: int
    event_type: str
    result: Any = None
    error: Optional[str] = None
    node_id: Optional[str] = None
    execution_time: float = 0.0
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class CallbackConfig:
    """Configuration for a callback."""
    callback: Callable
    event_type: str
    async_callback: bool = False
    max_retries: int = 3
    timeout: float = 30.0
    enabled: bool = True


class TaskCallbackManager:
    """
    Manager for task callbacks.

    Supports:
    - on_success: Called when task completes successfully
    - on_failure: Called when task fails
    - on_retry: Called when task is retried
    - on_timeout: Called when task times out
    - on_start: Called when task starts execution
    """

    def __init__(self):
        self._callbacks: dict[str, list[CallbackConfig]] = {
            "on_success": [],
            "on_failure": [],
            "on_retry": [],
            "on_timeout": [],
            "on_start": [],
            "on_complete": [],
        }
        self._task_callbacks: dict[int, dict[str, list[Callable]]] = {}

    def on_success(self, func: Callable) -> Callable:
        """Register a success callback."""
        self._register("on_success", func)
        return func

    def on_failure(self, func: Callable) -> Callable:
        """Register a failure callback."""
        self._register("on_failure", func)
        return func

    def on_retry(self, func: Callable) -> Callable:
        """Register a retry callback."""
        self._register("on_retry", func)
        return func

    def on_timeout(self, func: Callable) -> Callable:
        """Register a timeout callback."""
        self._register("on_timeout", func)
        return func

    def on_start(self, func: Callable) -> Callable:
        """Register a start callback."""
        self._register("on_start", func)
        return func

    def on_complete(self, func: Callable) -> Callable:
        """Register a completion callback (success or failure)."""
        self._register("on_complete", func)
        return func

    def _register(self, event_type: str, func: Callable) -> None:
        """Register a callback for an event type."""
        async_callback = asyncio.iscoroutinefunction(func)

        config = CallbackConfig(
            callback=func,
            event_type=event_type,
            async_callback=async_callback
        )

        self._callbacks[event_type].append(config)
        logger.debug(f"Registered {event_type} callback: {func.__name__}")

    def register_task_callback(
        self,
        task_id: int,
        event_type: str,
        callback: Callable
    ) -> None:
        """Register a callback for a specific task."""
        if task_id not in self._task_callbacks:
            self._task_callbacks[task_id] = {}

        if event_type not in self._task_callbacks[task_id]:
            self._task_callbacks[task_id][event_type] = []

        self._task_callbacks[task_id][event_type].append(callback)

    def trigger(
        self,
        event_type: str,
        context: CallbackContext
    ) -> None:
        """Trigger callbacks for an event."""
        callbacks = self._callbacks.get(event_type, [])

        task_callbacks = self._task_callbacks.get(context.task_id, {})
        callbacks = callbacks + [
            CallbackConfig(callback=cb, event_type=event_type)
            for cb in task_callbacks.get(event_type, [])
        ]

        for config in callbacks:
            if not config.enabled:
                continue

            try:
                if config.async_callback:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(
                            self._run_async_callback(config, context)
                        )
                    else:
                        loop.run_until_complete(
                            self._run_async_callback(config, context)
                        )
                else:
                    self._run_sync_callback(config, context)

            except Exception as e:
                logger.error(
                    f"Callback error for {event_type} on task {context.task_id}: {e}"
                )

    async def trigger_async(
        self,
        event_type: str,
        context: CallbackContext
    ) -> None:
        """Trigger callbacks asynchronously."""
        callbacks = self._callbacks.get(event_type, [])

        task_callbacks = self._task_callbacks.get(context.task_id, {})
        callbacks = callbacks + [
            CallbackConfig(callback=cb, event_type=event_type)
            for cb in task_callbacks.get(event_type, [])
        ]

        for config in callbacks:
            if not config.enabled:
                continue

            try:
                await self._run_async_callback(config, context)
            except Exception as e:
                logger.error(
                    f"Async callback error for {event_type} on task {context.task_id}: {e}"
                )

    def _run_sync_callback(
        self,
        config: CallbackConfig,
        context: CallbackContext
    ) -> None:
        """Run a synchronous callback."""
        config.callback(context)

    async def _run_async_callback(
        self,
        config: CallbackConfig,
        context: CallbackContext
    ) -> None:
        """Run an asynchronous callback."""
        await config.callback(context)

    def clear_task_callbacks(self, task_id: int) -> None:
        """Clear all callbacks for a task."""
        self._task_callbacks.pop(task_id, None)

    def get_stats(self) -> dict[str, Any]:
        """Get callback statistics."""
        return {
            "global_callbacks": {
                event: len(callbacks)
                for event, callbacks in self._callbacks.items()
            },
            "task_specific_count": len(self._task_callbacks),
        }


# Global callback manager
_callback_manager: Optional[TaskCallbackManager] = None


def get_callback_manager() -> TaskCallbackManager:
    """Get the global callback manager."""
    global _callback_manager
    if _callback_manager is None:
        _callback_manager = TaskCallbackManager()
    return _callback_manager


# Decorator shortcuts
task_callback = get_callback_manager()

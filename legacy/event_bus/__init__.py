"""
Event Bus for decoupled module communication.

This module provides an event-driven architecture for loose coupling
between components, inspired by:
- Django Signals
- Node.js EventEmitter
- Spring ApplicationEvent

Usage:
    bus = EventBus()

    # Subscribe to events
    @bus.on("task_completed")
    async def handle_task_completion(event):
        print(f"Task {event.data['task_id']} completed")

    # Publish events
    await bus.publish(Event("task_completed", {"task_id": 123}))
"""

import asyncio
import logging
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Union

logger = logging.getLogger(__name__)


class EventPriority(int, Enum):
    """Event handler priority."""

    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100


@dataclass
class Event:
    """Base event class."""

    event_type: str
    data: dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "data": self.data,
            "source": self.source,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class EventHandler:
    """Registered event handler."""

    handler: Callable
    event_type: str
    priority: int = EventPriority.NORMAL
    once: bool = False
    async_handler: bool = False

    def __lt__(self, other):
        return self.priority > other.priority


class EventBus:
    """
    Central event bus for pub/sub communication.

    Features:
    - Sync and async handler support
    - Priority-based handler execution
    - One-time handlers
    - Wildcard event matching
    - Event history
    """

    def __init__(self, history_size: int = 100, debug: bool = False):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: list[EventHandler] = []
        self._history: list[Event] = []
        self._history_size = history_size
        self._debug = debug
        self._lock = threading.Lock()

    def on(
        self, event_type: str, priority: int = EventPriority.NORMAL, once: bool = False
    ) -> Callable:
        """
        Decorator to register an event handler.

        Usage:
            @bus.on("task_completed")
            def handle(event):
                print(event.data)
        """

        def decorator(func: Callable) -> Callable:
            self.subscribe(event_type=event_type, handler=func, priority=priority, once=once)
            return func

        return decorator

    def subscribe(
        self,
        event_type: str,
        handler: Callable,
        priority: int = EventPriority.NORMAL,
        once: bool = False,
    ) -> None:
        """Subscribe a handler to an event type."""
        import asyncio

        async_handler = asyncio.iscoroutinefunction(handler)

        event_handler = EventHandler(
            handler=handler,
            event_type=event_type,
            priority=priority,
            once=once,
            async_handler=async_handler,
        )

        with self._lock:
            if event_type == "*":
                self._wildcard_handlers.append(event_handler)
            else:
                self._handlers[event_type].append(event_handler)
                self._handlers[event_type].sort(reverse=True)

        logger.debug(f"Subscribed handler to event '{event_type}'")

    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """Unsubscribe a handler from an event type."""
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            for i, eh in enumerate(handlers):
                if eh.handler == handler:
                    handlers.pop(i)
                    logger.debug(f"Unsubscribed handler from event '{event_type}'")
                    return True
        return False

    def publish(self, event: Union[Event, str], data: Optional[dict[str, Any]] = None) -> None:
        """
        Publish an event synchronously.

        Args:
            event: Event object or event type string
            data: Event data (if event is a string)
        """
        if isinstance(event, str):
            event = Event(event_type=event, data=data or {})

        self._record_event(event)

        handlers = self._get_handlers(event.event_type)

        for event_handler in handlers[:]:
            try:
                if event_handler.async_handler:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(event_handler.handler(event))
                    else:
                        loop.run_until_complete(event_handler.handler(event))
                else:
                    event_handler.handler(event)

                if event_handler.once:
                    self._remove_handler(event_handler)

            except Exception as e:
                logger.error(f"Error in event handler for '{event.event_type}': {e}")

        if self._debug:
            logger.debug(f"Published event '{event.event_type}' to {len(handlers)} handlers")

    async def publish_async(
        self, event: Union[Event, str], data: Optional[dict[str, Any]] = None
    ) -> None:
        """Publish an event asynchronously."""
        if isinstance(event, str):
            event = Event(event_type=event, data=data or {})

        self._record_event(event)

        handlers = self._get_handlers(event.event_type)

        for event_handler in handlers[:]:
            try:
                if event_handler.async_handler:
                    await event_handler.handler(event)
                else:
                    event_handler.handler(event)

                if event_handler.once:
                    self._remove_handler(event_handler)

            except Exception as e:
                logger.error(f"Error in async event handler for '{event.event_type}': {e}")

    def _get_handlers(self, event_type: str) -> list[EventHandler]:
        """Get all handlers for an event type."""
        handlers = list(self._handlers.get(event_type, []))
        handlers.extend(self._wildcard_handlers)
        handlers.sort(reverse=True)
        return handlers

    def _remove_handler(self, handler: EventHandler) -> None:
        """Remove a handler."""
        with self._lock:
            if handler.event_type == "*":
                if handler in self._wildcard_handlers:
                    self._wildcard_handlers.remove(handler)
            else:
                handlers = self._handlers.get(handler.event_type, [])
                if handler in handlers:
                    handlers.remove(handler)

    def _record_event(self, event: Event) -> None:
        """Record event in history."""
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_size:
                self._history.pop(0)

    def get_history(self, event_type: Optional[str] = None, limit: int = 10) -> list[Event]:
        """Get event history."""
        with self._lock:
            events = list(self._history)

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events[-limit:]

    def clear(self) -> None:
        """Clear all handlers and history."""
        with self._lock:
            self._handlers.clear()
            self._wildcard_handlers.clear()
            self._history.clear()


# Global event bus instance
_global_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus


# Predefined event types
class EventTypes:
    """Common event types."""

    # Task events
    TASK_SUBMITTED = "task_submitted"
    TASK_ASSIGNED = "task_assigned"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_RETRY = "task_retry"

    # Node events
    NODE_REGISTERED = "node_registered"
    NODE_HEARTBEAT = "node_heartbeat"
    NODE_OFFLINE = "node_offline"
    NODE_RECOVERED = "node_recovered"

    # System events
    SYSTEM_START = "system_start"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_ERROR = "system_error"

    # Scheduler events
    SCHEDULER_DECISION = "scheduler_decision"
    SCHEDULER_REBALANCE = "scheduler_rebalance"

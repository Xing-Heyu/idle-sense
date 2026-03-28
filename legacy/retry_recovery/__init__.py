"""
Task Retry and Recovery Module.

This module provides comprehensive retry mechanisms and fault recovery
capabilities inspired by Celery's retry system and Kubernetes pod restart policies.

Architecture Reference:
- Celery Retry: https://docs.celeryq.dev/en/stable/userguide/tasks.html#retrying
- Kubernetes Restart Policies: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/
"""
import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class RetryPolicy(str, Enum):
    """Retry policy enumeration."""
    NEVER = "never"
    ON_FAILURE = "on_failure"
    ALWAYS = "always"
    EXPONENTIAL_BACKOFF = "exponential_backoff"


class TaskRecoveryAction(str, Enum):
    """Recovery action enumeration."""
    RETRY = "retry"
    REASSIGN = "reassign"
    ABANDON = "abandon"
    CHECKPOINT_RESTORE = "checkpoint_restore"


@dataclass
class RetryConfig:
    """Configuration for task retry behavior."""
    max_retries: int = 3
    retry_delay: float = 1.0
    max_delay: float = 60.0
    exponential_backoff: bool = True
    backoff_factor: float = 2.0
    jitter: bool = True
    retry_exceptions: list[type[Exception]] = field(default_factory=list)
    skip_exceptions: list[type[Exception]] = field(default_factory=list)

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given retry attempt."""
        if self.exponential_backoff:
            delay = min(
                self.retry_delay * (self.backoff_factor ** attempt),
                self.max_delay
            )
        else:
            delay = self.retry_delay

        if self.jitter:
            delay = delay * (0.5 + random.random())

        return delay

    def should_retry(
        self,
        exception: Exception,
        attempt: int
    ) -> bool:
        """Determine if a task should be retried."""
        if attempt >= self.max_retries:
            return False

        if self.skip_exceptions:
            for skip_exc in self.skip_exceptions:
                if isinstance(exception, skip_exc):
                    return False

        if self.retry_exceptions:
            return any(isinstance(exception, retry_exc) for retry_exc in self.retry_exceptions)

        return True


@dataclass
class RetryState:
    """State tracking for retry attempts."""
    task_id: int
    attempt: int = 0
    last_error: Optional[str] = None
    last_attempt_time: float = 0.0
    next_retry_time: float = 0.0
    total_wait_time: float = 0.0
    history: list[dict[str, Any]] = field(default_factory=list)

    def record_attempt(self, error: Optional[Exception] = None):
        """Record a retry attempt."""
        self.attempt += 1
        self.last_attempt_time = time.time()
        self.last_error = str(error) if error else None

        self.history.append({
            "attempt": self.attempt,
            "time": self.last_attempt_time,
            "error": self.last_error,
        })

    def can_retry(self, max_retries: int) -> bool:
        """Check if more retries are allowed."""
        return self.attempt < max_retries


class RetryManager:
    """
    Manager for task retry logic.

    Usage:
        manager = RetryManager()

        # Configure retry for a task
        manager.configure(task_id=1, config=RetryConfig(max_retries=3))

        # Check if should retry
        if manager.should_retry(task_id=1, exception=ValueError("test")):
            delay = manager.get_retry_delay(task_id=1)
            time.sleep(delay)
            # retry task...
    """

    def __init__(self):
        self._configs: dict[int, RetryConfig] = {}
        self._states: dict[int, RetryState] = {}
        self._default_config = RetryConfig()

    def configure(
        self,
        task_id: int,
        config: Optional[RetryConfig] = None
    ) -> None:
        """Configure retry behavior for a task."""
        self._configs[task_id] = config or self._default_config
        self._states[task_id] = RetryState(task_id=task_id)

    def get_config(self, task_id: int) -> RetryConfig:
        """Get retry configuration for a task."""
        return self._configs.get(task_id, self._default_config)

    def get_state(self, task_id: int) -> Optional[RetryState]:
        """Get retry state for a task."""
        return self._states.get(task_id)

    def should_retry(
        self,
        task_id: int,
        exception: Exception
    ) -> bool:
        """Determine if a task should be retried."""
        config = self.get_config(task_id)
        state = self.get_state(task_id)

        if not state:
            state = RetryState(task_id=task_id)
            self._states[task_id] = state

        return config.should_retry(exception, state.attempt)

    def get_retry_delay(self, task_id: int) -> float:
        """Get delay before next retry."""
        config = self.get_config(task_id)
        state = self.get_state(task_id)

        attempt = state.attempt if state else 0
        delay = config.calculate_delay(attempt)

        if state:
            state.next_retry_time = time.time() + delay
            state.total_wait_time += delay

        return delay

    def record_attempt(
        self,
        task_id: int,
        exception: Optional[Exception] = None
    ) -> None:
        """Record a retry attempt."""
        state = self.get_state(task_id)

        if not state:
            state = RetryState(task_id=task_id)
            self._states[task_id] = state

        state.record_attempt(exception)

        if exception:
            logger.warning(
                f"Task {task_id} attempt {state.attempt} failed: {exception}"
            )
        else:
            logger.info(f"Task {task_id} attempt {state.attempt} recorded")

    def clear(self, task_id: int) -> None:
        """Clear retry state for a task."""
        self._configs.pop(task_id, None)
        self._states.pop(task_id, None)


def with_retry(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    exponential_backoff: bool = True,
    retry_exceptions: Optional[list[type[Exception]]] = None
) -> Callable:
    """
    Decorator for automatic retry on failure.

    Usage:
        @with_retry(max_retries=3, exponential_backoff=True)
        async def my_task():
            # ... task logic ...
            pass
    """
    def decorator(func: Callable) -> Callable:
        config = RetryConfig(
            max_retries=max_retries,
            retry_delay=retry_delay,
            exponential_backoff=exponential_backoff,
            retry_exceptions=retry_exceptions or []
        )

        async def async_wrapper(*args, **kwargs):
            attempt = 0
            last_error = None

            while attempt <= config.max_retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    if not config.should_retry(e, attempt):
                        raise

                    attempt += 1
                    delay = config.calculate_delay(attempt - 1)

                    logger.warning(
                        f"Retry {attempt}/{config.max_retries} for {func.__name__} "
                        f"after {delay:.2f}s: {e}"
                    )

                    await asyncio.sleep(delay)

            raise last_error

        def sync_wrapper(*args, **kwargs):
            attempt = 0
            last_error = None

            while attempt <= config.max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    if not config.should_retry(e, attempt):
                        raise

                    attempt += 1
                    delay = config.calculate_delay(attempt - 1)

                    logger.warning(
                        f"Retry {attempt}/{config.max_retries} for {func.__name__} "
                        f"after {delay:.2f}s: {e}"
                    )

                    time.sleep(delay)

            raise last_error

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


@dataclass
class FaultRecoveryConfig:
    """Configuration for fault recovery."""
    enable_checkpoint: bool = True
    checkpoint_interval: int = 60
    max_reassign_count: int = 3
    node_timeout_seconds: float = 180.0
    task_timeout_seconds: float = 3600.0
    recovery_delay: float = 5.0


class FaultRecoveryManager:
    """
    Manager for fault recovery and task reassignment.

    Handles:
    - Node failure detection and task reassignment
    - Task timeout detection
    - Checkpoint-based recovery
    """

    def __init__(
        self,
        config: Optional[FaultRecoveryConfig] = None,
        retry_manager: Optional[RetryManager] = None
    ):
        self.config = config or FaultRecoveryConfig()
        self.retry_manager = retry_manager or RetryManager()

        self._task_assignments: dict[int, str] = {}
        self._reassign_counts: dict[int, int] = {}
        self._checkpoints: dict[int, Any] = {}

    def assign_task(self, task_id: int, node_id: str) -> None:
        """Record task assignment to a node."""
        self._task_assignments[task_id] = node_id
        logger.debug(f"Task {task_id} assigned to node {node_id}")

    def unassign_task(self, task_id: int) -> None:
        """Remove task assignment."""
        self._task_assignments.pop(task_id, None)
        logger.debug(f"Task {task_id} unassigned")

    def get_assigned_node(self, task_id: int) -> Optional[str]:
        """Get the node assigned to a task."""
        return self._task_assignments.get(task_id)

    def handle_node_failure(
        self,
        node_id: str,
        get_running_tasks: Callable[[str], list[int]]
    ) -> list[dict[str, Any]]:
        """
        Handle node failure by marking tasks for recovery.

        Args:
            node_id: ID of the failed node
            get_running_tasks: Function to get running tasks on the node

        Returns:
            List of recovery actions for affected tasks
        """
        logger.warning(f"Handling failure for node {node_id}")

        running_tasks = get_running_tasks(node_id)
        recovery_actions = []

        for task_id in running_tasks:
            if self._task_assignments.get(task_id) == node_id:
                action = self._determine_recovery_action(task_id)

                recovery_actions.append({
                    "task_id": task_id,
                    "action": action.value,
                    "previous_node": node_id,
                })

                self._task_assignments.pop(task_id, None)

        return recovery_actions

    def _determine_recovery_action(
        self,
        task_id: int
    ) -> TaskRecoveryAction:
        """Determine the appropriate recovery action for a task."""
        reassign_count = self._reassign_counts.get(task_id, 0)

        if reassign_count >= self.config.max_reassign_count:
            return TaskRecoveryAction.ABANDON

        if task_id in self._checkpoints:
            return TaskRecoveryAction.CHECKPOINT_RESTORE

        return TaskRecoveryAction.REASSIGN

    def record_reassignment(self, task_id: int) -> None:
        """Record a task reassignment."""
        self._reassign_counts[task_id] = self._reassign_counts.get(task_id, 0) + 1
        logger.info(f"Task {task_id} reassigned (count: {self._reassign_counts[task_id]})")

    def save_checkpoint(
        self,
        task_id: int,
        state: Any
    ) -> None:
        """Save a checkpoint for a task."""
        self._checkpoints[task_id] = {
            "state": state,
            "timestamp": time.time(),
        }
        logger.debug(f"Checkpoint saved for task {task_id}")

    def get_checkpoint(self, task_id: int) -> Optional[Any]:
        """Get checkpoint state for a task."""
        checkpoint = self._checkpoints.get(task_id)
        return checkpoint["state"] if checkpoint else None

    def clear_checkpoint(self, task_id: int) -> None:
        """Clear checkpoint for a task."""
        self._checkpoints.pop(task_id, None)
        self._reassign_counts.pop(task_id, None)

    def get_recovery_stats(self) -> dict[str, Any]:
        """Get recovery statistics."""
        return {
            "active_assignments": len(self._task_assignments),
            "checkpoints_stored": len(self._checkpoints),
            "reassignment_counts": dict(self._reassign_counts),
        }


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by temporarily blocking requests
    to a failing service.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failing, requests are blocked
    - HALF_OPEN: Testing if service recovered
    """

    class State(str, Enum):
        CLOSED = "closed"
        OPEN = "open"
        HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = self.State.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0

    @property
    def state(self) -> State:
        """Get current state."""
        if self._state == self.State.OPEN and time.time() - self._last_failure_time >= self.recovery_timeout:
            self._state = self.State.HALF_OPEN
            self._success_count = 0

        return self._state

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        return self.state != self.State.OPEN

    def record_success(self) -> None:
        """Record a successful execution."""
        if self._state == self.State.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = self.State.CLOSED
                self._failure_count = 0
                logger.info("Circuit breaker closed (recovered)")
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed execution."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == self.State.HALF_OPEN:
            self._state = self.State.OPEN
            logger.warning("Circuit breaker opened (half-open failure)")
        elif self._failure_count >= self.failure_threshold:
            self._state = self.State.OPEN
            logger.warning(
                f"Circuit breaker opened (failures: {self._failure_count})"
            )


class RateLimiter:
    """
    Token bucket rate limiter.

    Limits the rate of operations to prevent overload.
    """

    def __init__(
        self,
        rate: float = 10.0,
        burst: int = 20
    ):
        self.rate = rate
        self.burst = burst
        self._tokens = float(burst)
        self._last_update = time.time()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_update
        self._tokens = min(
            self.burst,
            self._tokens + elapsed * self.rate
        )
        self._last_update = now

    def can_proceed(self) -> bool:
        """Check if an operation can proceed."""
        self._refill()
        return self._tokens >= 1.0

    def consume(self, tokens: int = 1) -> bool:
        """Consume tokens if available."""
        self._refill()

        if self._tokens >= tokens:
            self._tokens -= tokens
            return True

        return False

    def wait_for_token(self, timeout: float = 60.0) -> bool:
        """Wait until a token is available."""
        start = time.time()

        while time.time() - start < timeout:
            if self.consume():
                return True

            wait_time = (1.0 - self._tokens) / self.rate
            time.sleep(min(wait_time, 0.1))

        return False

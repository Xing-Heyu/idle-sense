"""
Unified Exception Hierarchy for Idle-Sense Project.

This module provides a consistent exception hierarchy for the entire project,
ensuring clear error messages and proper error handling across all modules.

Usage:
    from exceptions import (
        IdleSenseError,
        TaskError,
        TaskTimeoutError,
        NodeError,
        StorageError,
        SecurityError,
    )

    raise TaskTimeoutError("Task execution exceeded 300 seconds", task_id="task_123")
"""


class IdleSenseError(Exception):
    """Base exception for all Idle-Sense errors.

    All custom exceptions in the project should inherit from this class.

    Attributes:
        message: Human-readable error message
        details: Optional dictionary with additional error context
    """

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


# ==================== Task Related Errors ====================


class TaskError(IdleSenseError):
    """Base exception for task-related errors."""

    pass


class TaskNotFoundError(TaskError):
    """Raised when a task cannot be found."""

    def __init__(self, task_id: str, message: str = None):
        super().__init__(message or f"Task not found: {task_id}", details={"task_id": task_id})
        self.task_id = task_id


class TaskTimeoutError(TaskError):
    """Raised when a task execution exceeds the time limit."""

    def __init__(self, task_id: str, timeout: float, message: str = None):
        super().__init__(
            message or f"Task execution timed out after {timeout} seconds",
            details={"task_id": task_id, "timeout": timeout},
        )
        self.task_id = task_id
        self.timeout = timeout


class TaskExecutionError(TaskError):
    """Raised when a task fails during execution."""

    def __init__(self, task_id: str, reason: str, output: str = None, message: str = None):
        super().__init__(
            message or f"Task execution failed: {reason}",
            details={
                "task_id": task_id,
                "reason": reason,
                "output": output,
            },
        )
        self.task_id = task_id
        self.reason = reason
        self.output = output


class TaskValidationError(TaskError):
    """Raised when task validation fails."""

    def __init__(self, task_id: str, validation_errors: list, message: str = None):
        super().__init__(
            message or f"Task validation failed: {validation_errors}",
            details={"task_id": task_id, "validation_errors": validation_errors},
        )
        self.task_id = task_id
        self.validation_errors = validation_errors


class TaskResourceError(TaskError):
    """Raised when task resource requirements cannot be met."""

    def __init__(self, task_id: str, required: dict, available: dict, message: str = None):
        super().__init__(
            message or f"Insufficient resources: required {required}, available {available}",
            details={"task_id": task_id, "required": required, "available": available},
        )
        self.task_id = task_id
        self.required = required
        self.available = available


# ==================== Node Related Errors ====================


class NodeError(IdleSenseError):
    """Base exception for node-related errors."""

    pass


class NodeNotFoundError(NodeError):
    """Raised when a node cannot be found."""

    def __init__(self, node_id: str, message: str = None):
        super().__init__(message or f"Node not found: {node_id}", details={"node_id": node_id})
        self.node_id = node_id


class NodeOfflineError(NodeError):
    """Raised when attempting to interact with an offline node."""

    def __init__(self, node_id: str, last_seen: float = None, message: str = None):
        super().__init__(
            message or f"Node is offline: {node_id}",
            details={"node_id": node_id, "last_seen": last_seen},
        )
        self.node_id = node_id
        self.last_seen = last_seen


class NodeRegistrationError(NodeError):
    """Raised when node registration fails."""

    def __init__(self, node_id: str, reason: str, message: str = None):
        super().__init__(
            message or f"Node registration failed: {reason}",
            details={"node_id": node_id, "reason": reason},
        )
        self.node_id = node_id
        self.reason = reason


class NodeCapacityError(NodeError):
    """Raised when node capacity is exceeded."""

    def __init__(self, node_id: str, capacity: dict, current_usage: dict, message: str = None):
        super().__init__(
            message or f"Node capacity exceeded: {current_usage} > {capacity}",
            details={"node_id": node_id, "capacity": capacity, "current_usage": current_usage},
        )
        self.node_id = node_id
        self.capacity = capacity
        self.current_usage = current_usage


# ==================== Storage Related Errors ====================


class StorageError(IdleSenseError):
    """Base exception for storage-related errors."""

    pass


class StorageConnectionError(StorageError):
    """Raised when storage connection fails."""

    def __init__(self, backend: str, reason: str, message: str = None):
        super().__init__(
            message or f"Failed to connect to storage backend '{backend}': {reason}",
            details={"backend": backend, "reason": reason},
        )
        self.backend = backend
        self.reason = reason


class StorageKeyError(StorageError):
    """Raised when a storage key is not found."""

    def __init__(self, key: str, message: str = None):
        super().__init__(message or f"Key not found in storage: {key}", details={"key": key})
        self.key = key


class StorageBackendError(StorageError):
    """Raised when an unknown storage backend is requested."""

    def __init__(self, backend: str, available_backends: list = None, message: str = None):
        super().__init__(
            message or f"Unknown storage backend: {backend}. Available: {available_backends}",
            details={"backend": backend, "available_backends": available_backends or []},
        )
        self.backend = backend
        self.available_backends = available_backends


# ==================== Security Related Errors ====================


class SecurityError(IdleSenseError):
    """Base exception for security-related errors."""

    pass


class CodeSecurityError(SecurityError):
    """Raised when code fails security checks."""

    def __init__(self, code: str, violations: list, message: str = None):
        super().__init__(
            message or f"Code security check failed: {violations}",
            details={"violations": violations, "code_preview": code[:100] if code else None},
        )
        self.violations = violations


class SandboxError(SecurityError):
    """Raised when sandbox execution fails."""

    def __init__(self, sandbox_type: str, reason: str, message: str = None):
        super().__init__(
            message or f"Sandbox execution failed ({sandbox_type}): {reason}",
            details={"sandbox_type": sandbox_type, "reason": reason},
        )
        self.sandbox_type = sandbox_type
        self.reason = reason


class SandboxLevelError(SecurityError):
    """Raised when an unsupported sandbox level is requested."""

    def __init__(self, level: str, available_levels: list = None, message: str = None):
        super().__init__(
            message or f"Unsupported sandbox level: {level}. Available: {available_levels}",
            details={"level": level, "available_levels": available_levels or []},
        )
        self.level = level
        self.available_levels = available_levels


class AuthenticationError(SecurityError):
    """Raised when authentication fails."""

    def __init__(self, user_id: str = None, reason: str = None, message: str = None):
        super().__init__(
            message or f"Authentication failed: {reason}",
            details={"user_id": user_id, "reason": reason},
        )
        self.user_id = user_id
        self.reason = reason


class AuthorizationError(SecurityError):
    """Raised when authorization fails."""

    def __init__(self, user_id: str, resource: str, action: str, message: str = None):
        super().__init__(
            message or f"Authorization denied: user '{user_id}' cannot {action} on {resource}",
            details={"user_id": user_id, "resource": resource, "action": action},
        )
        self.user_id = user_id
        self.resource = resource
        self.action = action


# ==================== Network Related Errors ====================


class NetworkError(IdleSenseError):
    """Base exception for network-related errors."""

    pass


class ConnectionError(NetworkError):
    """Raised when network connection fails."""

    def __init__(self, host: str, port: int, reason: str = None, message: str = None):
        super().__init__(
            message or f"Failed to connect to {host}:{port}: {reason}",
            details={"host": host, "port": port, "reason": reason},
        )
        self.host = host
        self.port = port
        self.reason = reason


class P2PError(NetworkError):
    """Raised when P2P network operations fail."""

    def __init__(self, operation: str, reason: str, message: str = None):
        super().__init__(
            message or f"P2P operation '{operation}' failed: {reason}",
            details={"operation": operation, "reason": reason},
        )
        self.operation = operation
        self.reason = reason


class NATTraversalError(NetworkError):
    """Raised when NAT traversal fails."""

    def __init__(self, nat_type: str, reason: str, message: str = None):
        super().__init__(
            message or f"NAT traversal failed for type '{nat_type}': {reason}",
            details={"nat_type": nat_type, "reason": reason},
        )
        self.nat_type = nat_type
        self.reason = reason


# ==================== Economy Related Errors ====================


class EconomyError(IdleSenseError):
    """Base exception for economy-related errors."""

    pass


class InsufficientBalanceError(EconomyError):
    """Raised when account has insufficient balance."""

    def __init__(self, address: str, required: float, available: float, message: str = None):
        super().__init__(
            message or f"Insufficient balance: required {required}, available {available}",
            details={"address": address, "required": required, "available": available},
        )
        self.address = address
        self.required = required
        self.available = available


class StakingError(EconomyError):
    """Raised when staking operations fail."""

    def __init__(self, address: str, operation: str, reason: str, message: str = None):
        super().__init__(
            message or f"Staking operation '{operation}' failed for {address}: {reason}",
            details={"address": address, "operation": operation, "reason": reason},
        )
        self.address = address
        self.operation = operation
        self.reason = reason


class PaymentError(EconomyError):
    """Raised when payment operations fail."""

    def __init__(self, task_id: str, reason: str, message: str = None):
        super().__init__(
            message or f"Payment failed for task {task_id}: {reason}",
            details={"task_id": task_id, "reason": reason},
        )
        self.task_id = task_id
        self.reason = reason


# ==================== Configuration Related Errors ====================


class ConfigError(IdleSenseError):
    """Base exception for configuration-related errors."""

    pass


class ConfigNotFoundError(ConfigError):
    """Raised when configuration file is not found."""

    def __init__(self, config_path: str, message: str = None):
        super().__init__(
            message or f"Configuration file not found: {config_path}",
            details={"config_path": config_path},
        )
        self.config_path = config_path


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""

    def __init__(self, config_path: str, errors: list, message: str = None):
        super().__init__(
            message or f"Configuration validation failed: {errors}",
            details={"config_path": config_path, "errors": errors},
        )
        self.config_path = config_path
        self.errors = errors


# ==================== Serialization Related Errors ====================


class SerializationError(IdleSenseError):
    """Raised when serialization fails."""

    def __init__(self, data_type: str, reason: str, message: str = None):
        super().__init__(
            message or f"Serialization failed for type '{data_type}': {reason}",
            details={"data_type": data_type, "reason": reason},
        )
        self.data_type = data_type
        self.reason = reason


class DeserializationError(IdleSenseError):
    """Raised when deserialization fails."""

    def __init__(self, data: str, reason: str, message: str = None):
        super().__init__(
            message or f"Deserialization failed: {reason}",
            details={"data_preview": data[:100] if data else None, "reason": reason},
        )
        self.reason = reason


__all__ = [
    # Base
    "IdleSenseError",
    # Task
    "TaskError",
    "TaskNotFoundError",
    "TaskTimeoutError",
    "TaskExecutionError",
    "TaskValidationError",
    "TaskResourceError",
    # Node
    "NodeError",
    "NodeNotFoundError",
    "NodeOfflineError",
    "NodeRegistrationError",
    "NodeCapacityError",
    # Storage
    "StorageError",
    "StorageConnectionError",
    "StorageKeyError",
    "StorageBackendError",
    # Security
    "SecurityError",
    "CodeSecurityError",
    "SandboxError",
    "SandboxLevelError",
    "AuthenticationError",
    "AuthorizationError",
    # Network
    "NetworkError",
    "ConnectionError",
    "P2PError",
    "NATTraversalError",
    # Economy
    "EconomyError",
    "InsufficientBalanceError",
    "StakingError",
    "PaymentError",
    # Config
    "ConfigError",
    "ConfigNotFoundError",
    "ConfigValidationError",
    # Serialization
    "SerializationError",
    "DeserializationError",
]

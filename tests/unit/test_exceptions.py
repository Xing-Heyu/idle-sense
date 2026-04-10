"""
Unit tests for the unified exception hierarchy.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from legacy.exceptions import (
    AuthenticationError,
    AuthorizationError,
    CodeSecurityError,
    ConfigNotFoundError,
    ConfigValidationError,
    ConnectionError,
    DeserializationError,
    EconomyError,
    IdleSenseError,
    InsufficientBalanceError,
    NATTraversalError,
    NetworkError,
    NodeCapacityError,
    NodeError,
    NodeNotFoundError,
    NodeOfflineError,
    NodeRegistrationError,
    P2PError,
    PaymentError,
    SandboxError,
    SandboxLevelError,
    SecurityError,
    SerializationError,
    StakingError,
    StorageBackendError,
    StorageConnectionError,
    StorageError,
    StorageKeyError,
    TaskError,
    TaskExecutionError,
    TaskNotFoundError,
    TaskResourceError,
    TaskTimeoutError,
    TaskValidationError,
)


class TestIdleSenseError(unittest.TestCase):
    """Test base exception class."""

    def test_basic_creation(self):
        error = IdleSenseError("Test error message")
        self.assertEqual(str(error), "Test error message")
        self.assertEqual(error.message, "Test error message")
        self.assertEqual(error.details, {})

    def test_with_details(self):
        details = {"key": "value", "count": 42}
        error = IdleSenseError("Test error", details=details)
        self.assertEqual(error.details, details)

    def test_to_dict(self):
        error = IdleSenseError("Test error", details={"extra": "info"})
        result = error.to_dict()

        self.assertEqual(result["error"], "IdleSenseError")
        self.assertEqual(result["message"], "Test error")
        self.assertEqual(result["details"], {"extra": "info"})


class TestTaskErrors(unittest.TestCase):
    """Test task-related exceptions."""

    def test_task_not_found_error(self):
        error = TaskNotFoundError("task_123")

        self.assertEqual(error.task_id, "task_123")
        self.assertIn("task_123", str(error))
        self.assertEqual(error.details["task_id"], "task_123")

    def test_task_timeout_error(self):
        error = TaskTimeoutError("task_123", timeout=300.0)

        self.assertEqual(error.task_id, "task_123")
        self.assertEqual(error.timeout, 300.0)
        self.assertIn("300", str(error))
        self.assertEqual(error.details["timeout"], 300.0)

    def test_task_execution_error(self):
        error = TaskExecutionError(
            task_id="task_123", reason="Division by zero", output="Error: division by zero"
        )

        self.assertEqual(error.task_id, "task_123")
        self.assertEqual(error.reason, "Division by zero")
        self.assertEqual(error.output, "Error: division by zero")

    def test_task_validation_error(self):
        errors = ["Invalid code", "Missing required field"]
        error = TaskValidationError("task_123", validation_errors=errors)

        self.assertEqual(error.validation_errors, errors)
        self.assertEqual(error.details["validation_errors"], errors)

    def test_task_resource_error(self):
        error = TaskResourceError(
            task_id="task_123",
            required={"cpu": 4.0, "memory": 8192},
            available={"cpu": 2.0, "memory": 4096},
        )

        self.assertEqual(error.required, {"cpu": 4.0, "memory": 8192})
        self.assertEqual(error.available, {"cpu": 2.0, "memory": 4096})


class TestNodeErrors(unittest.TestCase):
    """Test node-related exceptions."""

    def test_node_not_found_error(self):
        error = NodeNotFoundError("node_456")

        self.assertEqual(error.node_id, "node_456")
        self.assertIn("node_456", str(error))

    def test_node_offline_error(self):
        error = NodeOfflineError("node_456", last_seen=1700000000.0)

        self.assertEqual(error.node_id, "node_456")
        self.assertEqual(error.last_seen, 1700000000.0)

    def test_node_registration_error(self):
        error = NodeRegistrationError("node_456", reason="Invalid token")

        self.assertEqual(error.node_id, "node_456")
        self.assertEqual(error.reason, "Invalid token")

    def test_node_capacity_error(self):
        error = NodeCapacityError(
            node_id="node_456",
            capacity={"cpu": 8.0, "memory": 16384},
            current_usage={"cpu": 7.5, "memory": 15000},
        )

        self.assertEqual(error.capacity, {"cpu": 8.0, "memory": 16384})
        self.assertEqual(error.current_usage, {"cpu": 7.5, "memory": 15000})


class TestStorageErrors(unittest.TestCase):
    """Test storage-related exceptions."""

    def test_storage_connection_error(self):
        error = StorageConnectionError("redis", reason="Connection refused")

        self.assertEqual(error.backend, "redis")
        self.assertEqual(error.reason, "Connection refused")

    def test_storage_key_error(self):
        error = StorageKeyError("missing_key")

        self.assertEqual(error.key, "missing_key")
        self.assertIn("missing_key", str(error))

    def test_storage_backend_error(self):
        error = StorageBackendError(
            backend="unknown", available_backends=["memory", "redis", "sqlite"]
        )

        self.assertEqual(error.backend, "unknown")
        self.assertEqual(error.available_backends, ["memory", "redis", "sqlite"])


class TestSecurityErrors(unittest.TestCase):
    """Test security-related exceptions."""

    def test_code_security_error(self):
        violations = ["os module import", "subprocess usage"]
        error = CodeSecurityError("import os", violations=violations)

        self.assertEqual(error.violations, violations)

    def test_sandbox_error(self):
        error = SandboxError("docker", reason="Container failed to start")

        self.assertEqual(error.sandbox_type, "docker")
        self.assertEqual(error.reason, "Container failed to start")

    def test_sandbox_level_error(self):
        error = SandboxLevelError(
            level="invalid", available_levels=["basic", "container", "gvisor"]
        )

        self.assertEqual(error.level, "invalid")
        self.assertEqual(error.available_levels, ["basic", "container", "gvisor"])

    def test_authentication_error(self):
        error = AuthenticationError(user_id="user_123", reason="Invalid password")

        self.assertEqual(error.user_id, "user_123")
        self.assertEqual(error.reason, "Invalid password")

    def test_authorization_error(self):
        error = AuthorizationError(user_id="user_123", resource="admin_panel", action="write")

        self.assertEqual(error.user_id, "user_123")
        self.assertEqual(error.resource, "admin_panel")
        self.assertEqual(error.action, "write")


class TestNetworkErrors(unittest.TestCase):
    """Test network-related exceptions."""

    def test_connection_error(self):
        error = ConnectionError(host="localhost", port=8000, reason="Connection refused")

        self.assertEqual(error.host, "localhost")
        self.assertEqual(error.port, 8000)
        self.assertEqual(error.reason, "Connection refused")

    def test_p2p_error(self):
        error = P2PError(operation="find_node", reason="Timeout")

        self.assertEqual(error.operation, "find_node")
        self.assertEqual(error.reason, "Timeout")

    def test_nat_traversal_error(self):
        error = NATTraversalError(nat_type="symmetric", reason="Hole punching failed")

        self.assertEqual(error.nat_type, "symmetric")
        self.assertEqual(error.reason, "Hole punching failed")


class TestEconomyErrors(unittest.TestCase):
    """Test economy-related exceptions."""

    def test_insufficient_balance_error(self):
        error = InsufficientBalanceError(address="addr_123", required=100.0, available=50.0)

        self.assertEqual(error.address, "addr_123")
        self.assertEqual(error.required, 100.0)
        self.assertEqual(error.available, 50.0)

    def test_staking_error(self):
        error = StakingError(
            address="addr_123", operation="unstake", reason="Lock period not expired"
        )

        self.assertEqual(error.address, "addr_123")
        self.assertEqual(error.operation, "unstake")
        self.assertEqual(error.reason, "Lock period not expired")

    def test_payment_error(self):
        error = PaymentError(task_id="task_123", reason="Insufficient funds")

        self.assertEqual(error.task_id, "task_123")
        self.assertEqual(error.reason, "Insufficient funds")


class TestConfigErrors(unittest.TestCase):
    """Test configuration-related exceptions."""

    def test_config_not_found_error(self):
        error = ConfigNotFoundError("/path/to/config.yaml")

        self.assertEqual(error.config_path, "/path/to/config.yaml")

    def test_config_validation_error(self):
        errors = ["Missing required field: host", "Invalid port number"]
        error = ConfigValidationError("/path/to/config.yaml", errors=errors)

        self.assertEqual(error.config_path, "/path/to/config.yaml")
        self.assertEqual(error.errors, errors)


class TestSerializationErrors(unittest.TestCase):
    """Test serialization-related exceptions."""

    def test_serialization_error(self):
        error = SerializationError(
            data_type="CustomObject", reason="Object is not JSON serializable"
        )

        self.assertEqual(error.data_type, "CustomObject")
        self.assertEqual(error.reason, "Object is not JSON serializable")

    def test_deserialization_error(self):
        error = DeserializationError(data='{"invalid": json}', reason="Invalid JSON format")

        self.assertEqual(error.reason, "Invalid JSON format")


class TestExceptionInheritance(unittest.TestCase):
    """Test exception inheritance hierarchy."""

    def test_task_error_inherits_from_base(self):
        self.assertTrue(issubclass(TaskError, IdleSenseError))
        self.assertTrue(issubclass(TaskTimeoutError, TaskError))
        self.assertTrue(issubclass(TaskTimeoutError, IdleSenseError))

    def test_node_error_inherits_from_base(self):
        self.assertTrue(issubclass(NodeError, IdleSenseError))
        self.assertTrue(issubclass(NodeNotFoundError, NodeError))

    def test_storage_error_inherits_from_base(self):
        self.assertTrue(issubclass(StorageError, IdleSenseError))
        self.assertTrue(issubclass(StorageConnectionError, StorageError))

    def test_security_error_inherits_from_base(self):
        self.assertTrue(issubclass(SecurityError, IdleSenseError))
        self.assertTrue(issubclass(SandboxError, SecurityError))

    def test_network_error_inherits_from_base(self):
        self.assertTrue(issubclass(NetworkError, IdleSenseError))
        self.assertTrue(issubclass(P2PError, NetworkError))

    def test_economy_error_inherits_from_base(self):
        self.assertTrue(issubclass(EconomyError, IdleSenseError))
        self.assertTrue(issubclass(InsufficientBalanceError, EconomyError))


class TestCustomMessages(unittest.TestCase):
    """Test custom error messages."""

    def test_custom_message_preserved(self):
        error = TaskNotFoundError("task_123", message="Custom not found message")
        self.assertEqual(str(error), "Custom not found message")

    def test_custom_message_in_details(self):
        error = StorageConnectionError(
            "redis", "Connection refused", message="Failed to connect to Redis server"
        )
        self.assertIn("Redis", str(error))


if __name__ == "__main__":
    unittest.main(verbosity=2)

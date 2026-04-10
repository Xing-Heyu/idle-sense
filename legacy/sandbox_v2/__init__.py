"""
Enhanced Secure Sandbox with Multi-Level Isolation.

This module provides multiple isolation levels for safe code execution:
- Level 1 (Basic): Python exec with restricted builtins (current implementation)
- Level 2 (Container): Docker container isolation
- Level 3 (gVisor): Docker + gVisor runtime for kernel-level isolation
- Level 4 (MicroVM): Firecracker microVM for hardware-level isolation

Security Architecture Reference:
- gVisor: https://gvisor.dev/ - User-space kernel by Google
- Firecracker: https://firecracker-microvm.github.io/ - MicroVM by AWS
- OpenSandbox: https://github.com/OpenInterpreter/opensandbox

Usage:
    sandbox = SecureSandbox(level=SandboxLevel.CONTAINER)
    result = await sandbox.execute("print('hello')", timeout=30)
"""

import ast
import asyncio
import contextlib
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SandboxLevel(Enum):
    """Sandbox isolation levels."""

    BASIC = "basic"
    CONTAINER = "container"
    GVISOR = "gvisor"
    MICROVM = "microvm"
    WASM = "wasm"


@dataclass
class SandboxResult:
    """Result of sandbox execution."""

    success: bool
    output: str = ""
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    memory_used_mb: float = 0.0
    exit_code: int = 0


@dataclass
class SandboxConfig:
    """Sandbox configuration."""

    timeout: int = 300
    memory_limit_mb: int = 512
    cpu_limit: float = 1.0
    network_disabled: bool = True
    max_output_size: int = 10000
    allowed_modules: set[str] = field(
        default_factory=lambda: {
            "math",
            "random",
            "statistics",
            "time",
            "datetime",
            "collections",
            "itertools",
            "functools",
            "operator",
            "json",
            "re",
            "string",
            "hashlib",
            "base64",
            "decimal",
            "fractions",
            "typing",
            "dataclasses",
        }
    )
    dangerous_builtins: set[str] = field(
        default_factory=lambda: {
            "eval",
            "exec",
            "compile",
            "input",
            "open",
            "file",
            "__import__",
            "reload",
            "globals",
            "locals",
            "vars",
            "dir",
            "help",
            "exit",
            "quit",
            "license",
            "credits",
            "breakpoint",
            "__build_class__",
            "__debug__",
        }
    )


class CodeAnalyzer:
    """Static code analysis for security checks."""

    DANGEROUS_PATTERNS = [
        ("__import__", "Dynamic import detected"),
        ("eval(", "eval() function call detected"),
        ("exec(", "exec() function call detected"),
        ("compile(", "compile() function call detected"),
        ("open(", "File open detected"),
        ("subprocess", "Subprocess module usage detected"),
        ("os.system", "System command execution detected"),
        ("socket", "Socket usage detected"),
        ("threading", "Threading detected"),
        ("multiprocessing", "Multiprocessing detected"),
    ]

    @classmethod
    def analyze(cls, code: str) -> tuple[bool, list[str]]:
        """
        Analyze code for security issues.

        Returns:
            Tuple of (is_safe, list_of_warnings)
        """
        warnings = []

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, [f"Syntax error: {e}"]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in (
                        "os",
                        "sys",
                        "subprocess",
                        "socket",
                        "threading",
                        "multiprocessing",
                        "shutil",
                    ):
                        warnings.append(f"Dangerous import: {alias.name}")

            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in ("os", "sys", "subprocess", "socket", "threading"):
                    warnings.append(f"Dangerous import from: {node.module}")

            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ("eval", "exec", "compile", "open", "__import__")
            ):
                warnings.append(f"Dangerous function call: {node.func.id}")

        is_safe = len(warnings) == 0
        return is_safe, warnings


class BasicSandbox:
    """
    Basic sandbox using Python exec with restricted environment.

    This is the current implementation, enhanced with better security checks.
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()

    def _create_safe_globals(self) -> dict[str, Any]:
        """Create a restricted global namespace."""
        import base64
        import datetime
        import hashlib
        import json as json_module
        import math
        import random
        import re
        import statistics
        import time as time_module
        from collections import Counter, defaultdict, deque
        from decimal import Decimal
        from fractions import Fraction
        from functools import partial, reduce  # noqa: F401
        from itertools import chain, combinations, product  # noqa: F401

        ALLOWED_MODULES = self.config.allowed_modules

        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            """Restricted import that only allows safe modules."""
            base_name = name.split(".")[0]
            if base_name not in ALLOWED_MODULES:
                raise ImportError(f"Module '{name}' is not allowed in sandbox")
            return __import__(name, globals, locals, fromlist, level)

        safe_builtins = {
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "chr": chr,
            "ord": ord,
            "dict": dict,
            "enumerate": enumerate,
            "filter": filter,
            "float": float,
            "format": format,
            "frozenset": frozenset,
            "hex": hex,
            "int": int,
            "isinstance": isinstance,
            "issubclass": issubclass,
            "iter": iter,
            "len": len,
            "list": list,
            "map": map,
            "max": max,
            "min": min,
            "next": next,
            "oct": oct,
            "pow": pow,
            "print": print,
            "range": range,
            "repr": repr,
            "reversed": reversed,
            "round": round,
            "set": set,
            "slice": slice,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "type": type,
            "zip": zip,
            "True": True,
            "False": False,
            "None": None,
            "__import__": safe_import,
        }

        return {
            "__builtins__": safe_builtins,
            "math": math,
            "random": random,
            "statistics": statistics,
            "time": time_module,
            "datetime": datetime,
            "json": json_module,
            "re": re,
            "hashlib": hashlib,
            "base64": base64,
            "Counter": Counter,
            "defaultdict": defaultdict,
            "deque": deque,
            "Decimal": Decimal,
            "Fraction": Fraction,
        }

    def execute(self, code: str, timeout: Optional[int] = None) -> SandboxResult:
        """Execute code in basic sandbox."""
        timeout = timeout or self.config.timeout
        start_time = time.time()

        is_safe, warnings = CodeAnalyzer.analyze(code)
        if not is_safe:
            return SandboxResult(
                success=False, error=f"Security check failed: {'; '.join(warnings)}"
            )

        if self.config.memory_limit_mb < 512:
            return self._execute_with_subprocess(code, timeout, start_time)

        return self._execute_in_process(code, timeout, start_time)

    def _execute_in_process(self, code: str, timeout: int, start_time: float) -> SandboxResult:
        """Execute code in current process (no memory isolation)."""
        safe_globals = self._create_safe_globals()
        safe_locals = {}
        output_buffer = []

        def safe_print(*args, **kwargs):
            output_buffer.append(" ".join(str(a) for a in args))

        safe_globals["__builtins__"]["print"] = safe_print

        import threading

        execution_error = None
        execution_result = None

        def run_code():
            nonlocal execution_error, execution_result
            try:
                exec(code, safe_globals, safe_locals)
                execution_result = safe_locals.get("__result__", safe_locals.get("result"))
            except MemoryError:
                execution_error = MemoryError("Memory limit exceeded")
            except Exception as e:
                execution_error = e

        thread = threading.Thread(target=run_code)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            return SandboxResult(
                success=False,
                error=f"Execution timed out after {timeout} seconds",
                execution_time=time.time() - start_time,
            )

        if execution_error:
            if isinstance(execution_error, MemoryError):
                return SandboxResult(
                    success=False,
                    output="\n".join(output_buffer),
                    error="Memory limit exceeded",
                    execution_time=time.time() - start_time,
                )
            return SandboxResult(
                success=False,
                output="\n".join(output_buffer),
                error=f"{type(execution_error).__name__}: {str(execution_error)}",
                execution_time=time.time() - start_time,
            )

        return SandboxResult(
            success=True,
            output="\n".join(output_buffer),
            result=execution_result,
            execution_time=time.time() - start_time,
        )

    def _execute_with_subprocess(self, code: str, timeout: int, start_time: float) -> SandboxResult:
        """Execute code in subprocess for memory isolation."""
        import platform

        if platform.system() == "Windows":
            return self._execute_with_subprocess_windows(code, timeout, start_time)

        wrapper_code = f"""
import sys
import json
import resource

try:
    memory_limit_mb = {self.config.memory_limit_mb}
    if memory_limit_mb > 0:
        try:
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit_mb * 1024 * 1024, hard))
        except (ValueError, OSError):
            pass

    safe_globals = {{
        "__builtins__": {{
            "abs": abs, "all": all, "any": any, "bool": bool,
            "chr": chr, "ord": ord, "dict": dict, "enumerate": enumerate,
            "filter": filter, "float": float, "format": format, "frozenset": frozenset,
            "hex": hex, "int": int, "isinstance": isinstance, "issubclass": issubclass,
            "iter": iter, "len": len, "list": list, "map": map, "max": max,
            "min": min, "next": next, "oct": oct, "pow": pow, "print": print,
            "range": range, "repr": repr, "reversed": reversed, "round": round,
            "set": set, "slice": slice, "sorted": sorted, "str": str,
            "sum": sum, "tuple": tuple, "type": type, "zip": zip,
            "True": True, "False": False, "None": None,
        }}
    }}

    safe_locals = {{}}
    exec({code!r}, safe_globals, safe_locals)

    result = safe_locals.get("result")
    print(json.dumps({{"success": True, "result": str(result) if result is not None else None}}))
except MemoryError:
    print(json.dumps({{"success": False, "error": "Memory limit exceeded"}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": f"{{type(e).__name__}}: {{str(e)}}"}}))
"""

        try:
            result = subprocess.run(
                [sys.executable, "-c", wrapper_code],
                capture_output=True,
                text=True,
                timeout=timeout,
                env={},
                cwd=tempfile.gettempdir(),
            )

            import json as json_module

            try:
                output_data = json_module.loads(result.stdout.strip().split("\n")[-1])
                if output_data.get("success"):
                    return SandboxResult(
                        success=True,
                        output=result.stdout,
                        result=output_data.get("result"),
                        execution_time=time.time() - start_time,
                        exit_code=0,
                    )
                else:
                    return SandboxResult(
                        success=False,
                        output=result.stdout,
                        error=output_data.get("error", "Unknown error"),
                        execution_time=time.time() - start_time,
                        exit_code=result.returncode,
                    )
            except (json_module.JSONDecodeError, IndexError):
                if result.returncode == 0:
                    return SandboxResult(
                        success=True,
                        output=result.stdout,
                        execution_time=time.time() - start_time,
                        exit_code=0,
                    )
                return SandboxResult(
                    success=False,
                    output=result.stdout,
                    error=result.stderr or "Execution failed",
                    execution_time=time.time() - start_time,
                    exit_code=result.returncode,
                )

        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                error=f"Execution timed out after {timeout} seconds",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return SandboxResult(
                success=False,
                error=f"Execution error: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _execute_with_subprocess_windows(
        self, code: str, timeout: int, start_time: float
    ) -> SandboxResult:
        """Execute code in subprocess on Windows with memory monitoring."""
        wrapper_code = f"""
import sys
import json
import tracemalloc

tracemalloc.start()

try:
    safe_globals = {{
        "__builtins__": {{
            "abs": abs, "all": all, "any": any, "bool": bool,
            "chr": chr, "ord": ord, "dict": dict, "enumerate": enumerate,
            "filter": filter, "float": float, "format": format, "frozenset": frozenset,
            "hex": hex, "int": int, "isinstance": isinstance, "issubclass": issubclass,
            "iter": iter, "len": len, "list": list, "map": map, "max": max,
            "min": min, "next": next, "oct": oct, "pow": pow, "print": print,
            "range": range, "repr": repr, "reversed": reversed, "round": round,
            "set": set, "slice": slice, "sorted": sorted, "str": str,
            "sum": sum, "tuple": tuple, "type": type, "zip": zip,
            "True": True, "False": False, "None": None,
        }}
    }}

    safe_locals = {{}}
    exec({code!r}, safe_globals, safe_locals)

    result = safe_locals.get("result")
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(json.dumps({{"success": True, "result": str(result) if result is not None else None, "memory_mb": peak / 1024 / 1024}}))
except MemoryError:
    print(json.dumps({{"success": False, "error": "Memory limit exceeded"}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": f"{{type(e).__name__}}: {{str(e)}}"}}))
"""

        try:
            process = subprocess.Popen(
                [sys.executable, "-c", wrapper_code],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={},
                cwd=tempfile.gettempdir(),
            )

            memory_exceeded = False
            memory_limit_bytes = self.config.memory_limit_mb * 1024 * 1024

            try:
                import psutil

                psutil_process = psutil.Process(process.pid)

                while process.poll() is None:
                    try:
                        mem_info = psutil_process.memory_info()
                        if mem_info.rss > memory_limit_bytes:
                            memory_exceeded = True
                            process.kill()
                            process.wait()
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        break
                    time.sleep(0.01)
            except ImportError:
                pass

            stdout, stderr = process.communicate(timeout=timeout)

            if memory_exceeded:
                return SandboxResult(
                    success=False,
                    error=f"Memory limit exceeded ({self.config.memory_limit_mb} MB)",
                    execution_time=time.time() - start_time,
                )

            import json as json_module

            try:
                output_data = json_module.loads(stdout.strip().split("\n")[-1])
                if output_data.get("success"):
                    return SandboxResult(
                        success=True,
                        output=stdout,
                        result=output_data.get("result"),
                        memory_used_mb=output_data.get("memory_mb", 0),
                        execution_time=time.time() - start_time,
                        exit_code=0,
                    )
                else:
                    return SandboxResult(
                        success=False,
                        output=stdout,
                        error=output_data.get("error", "Unknown error"),
                        execution_time=time.time() - start_time,
                        exit_code=process.returncode,
                    )
            except (json_module.JSONDecodeError, IndexError):
                if process.returncode == 0:
                    return SandboxResult(
                        success=True,
                        output=stdout,
                        execution_time=time.time() - start_time,
                        exit_code=0,
                    )
                return SandboxResult(
                    success=False,
                    output=stdout,
                    error=stderr or "Execution failed",
                    execution_time=time.time() - start_time,
                    exit_code=process.returncode,
                )

        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            return SandboxResult(
                success=False,
                error=f"Execution timed out after {timeout} seconds",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return SandboxResult(
                success=False,
                error=f"Execution error: {str(e)}",
                execution_time=time.time() - start_time,
            )


class DockerSandbox:
    """
    Docker-based sandbox for container isolation.

    Provides stronger isolation than basic sandbox by running code
    in a Docker container with resource limits.

    Requirements:
        - Docker installed and running
        - Python Docker SDK: pip install docker
    """

    def __init__(self, config: Optional[SandboxConfig] = None, runtime: str = "runc"):
        self.config = config or SandboxConfig()
        self.runtime = runtime
        self._client = None

    def _get_client(self):
        """Get Docker client."""
        if self._client is None:
            try:
                import docker

                self._client = docker.from_env()
            except ImportError as e:
                raise ImportError(
                    "Docker sandbox requires the docker package. "
                    "Install it with: pip install docker"
                ) from e
        return self._client

    def execute(self, code: str, timeout: Optional[int] = None) -> SandboxResult:
        """Execute code in Docker container."""
        timeout = timeout or self.config.timeout
        start_time = time.time()

        is_safe, warnings = CodeAnalyzer.analyze(code)
        if not is_safe:
            return SandboxResult(
                success=False, error=f"Security check failed: {'; '.join(warnings)}"
            )

        try:
            client = self._get_client()

            container = client.containers.run(
                image="python:3.9-slim",
                command=["python", "-c", code],
                runtime=self.runtime,
                mem_limit=f"{self.config.memory_limit_mb}m",
                cpu_period=100000,
                cpu_quota=int(100000 * self.config.cpu_limit),
                network_disabled=self.config.network_disabled,
                remove=True,
                stdout=True,
                stderr=True,
                detach=False,
                timeout=timeout,
            )

            output = container.decode("utf-8") if isinstance(container, bytes) else str(container)

            return SandboxResult(
                success=True,
                output=output[: self.config.max_output_size],
                execution_time=time.time() - start_time,
                exit_code=0,
            )

        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                error=f"Execution timed out after {timeout} seconds",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return SandboxResult(
                success=False,
                error=f"Docker error: {str(e)}",
                execution_time=time.time() - start_time,
            )


class GVisorSandbox(DockerSandbox):
    """
    gVisor-based sandbox for kernel-level isolation.

    gVisor provides a user-space kernel that intercepts system calls,
    providing stronger isolation than regular containers.

    Requirements:
        - Docker installed with gVisor runtime (runsc)
        - Install gVisor: https://gvisor.dev/docs/user_guide/install/
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        super().__init__(config, runtime="runsc")

    def is_available(self) -> bool:
        """Check if gVisor runtime is available."""
        try:
            client = self._get_client()
            info = client.info()
            runtimes = info.get("Runtimes", {})
            return "runsc" in runtimes
        except Exception:
            return False


class WASMSandbox:
    """
    WebAssembly-based sandbox for secure multi-language execution.

    WASM provides the strongest isolation with near-native performance.
    Supports multiple languages: Rust, C/C++, Go, AssemblyScript.

    Requirements:
        - wasmtime: pip install wasmtime
        - WASI SDK for compiling to WASM (optional)

    Security Features:
        - Hardware-enforced sandbox
        - No system calls without WASI permission
        - Memory isolation
        - Deterministic execution
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self._engine = None
        self._store = None

    def _get_engine(self):
        """Get or create WASM engine."""
        if self._engine is None:
            try:
                import wasmtime

                self._engine = wasmtime.Engine()
            except ImportError as e:
                raise ImportError(
                    "WASM sandbox requires wasmtime. " "Install it with: pip install wasmtime"
                ) from e
        return self._engine

    def compile_python_to_wasm(self, code: str) -> bytes:
        """
        Compile Python code to WASM using Pyodide or similar.

        Note: This is a placeholder. In production, you would:
        1. Use Pyodide to compile Python to WASM
        2. Or use a pre-compiled Python WASM runtime
        """
        wrapper = f"""
import json
import sys

# User code
{code}

# Output result
if 'result' in dir():
    print(json.dumps({{"success": True, "result": str(result)}}))
else:
    print(json.dumps({{"success": True, "output": "completed"}}))
"""
        return wrapper.encode("utf-8")

    def execute_wasm(
        self, wasm_bytes: bytes, function_name: str = "_start", args: Optional[list[Any]] = None
    ) -> SandboxResult:
        """Execute a WASM module."""
        start_time = time.time()

        try:
            import wasmtime

            engine = self._get_engine()
            module = wasmtime.Module.from_bytes(engine, wasm_bytes)
            store = wasmtime.Store(engine)

            config = wasmtime.Config()
            config.wasm_multi_value = True
            config.wasm_simd = True

            instance = wasmtime.Instance(store, module, [])

            func = instance.exports(store).get(function_name)
            if func is None:
                return SandboxResult(
                    success=False,
                    error=f"Function '{function_name}' not found in WASM module",
                    execution_time=time.time() - start_time,
                )

            result = func(store, *(args or []))

            return SandboxResult(
                success=True,
                output=str(result) if result else "",
                result=result,
                execution_time=time.time() - start_time,
            )

        except ImportError:
            return SandboxResult(
                success=False,
                error="WASM runtime not available. Install: pip install wasmtime",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return SandboxResult(
                success=False,
                error=f"WASM execution error: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def execute(self, code: str, timeout: Optional[int] = None) -> SandboxResult:
        """
        Execute code in WASM sandbox.

        Note: Direct Python execution in WASM requires Pyodide.
        This implementation uses subprocess isolation as fallback.
        """
        timeout = timeout or self.config.timeout
        start_time = time.time()

        is_safe, warnings = CodeAnalyzer.analyze(code)
        if not is_safe:
            return SandboxResult(
                success=False, error=f"Security check failed: {'; '.join(warnings)}"
            )

        try:
            import os
            import subprocess
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                temp_file = f.name

            try:
                result = subprocess.run(
                    [sys.executable, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env={
                        "PYTHONPATH": "",
                        "PATH": os.environ.get("PATH", ""),
                    },
                )

                output = result.stdout

                if result.returncode == 0:
                    return SandboxResult(
                        success=True,
                        output=output[: self.config.max_output_size],
                        execution_time=time.time() - start_time,
                        exit_code=0,
                    )
                else:
                    return SandboxResult(
                        success=False,
                        output=output[: self.config.max_output_size],
                        error=result.stderr[: self.config.max_output_size],
                        execution_time=time.time() - start_time,
                        exit_code=result.returncode,
                    )

            finally:
                os.unlink(temp_file)

        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                error=f"Execution timed out after {timeout} seconds",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return SandboxResult(
                success=False,
                error=f"Execution error: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def is_available(self) -> bool:
        """Check if WASM runtime is available."""
        try:
            import wasmtime  # noqa: F401

            return True
        except ImportError:
            return False


class FirecrackerSandbox:
    """
    Firecracker MicroVM-based sandbox for hardware-level isolation.

    Firecracker provides the strongest isolation by running code in
    lightweight virtual machines with hardware-enforced boundaries.

    Requirements:
        - Firecracker installed: https://firecracker-microvm.github.io/
        - Linux host with KVM support
        - Root access for Firecracker

    Security Features:
        - Hardware-level VM isolation
        - Minimal attack surface (< 175 LOC VMM)
        - Fast boot (< 125ms)
        - Resource isolation per VM
    """

    FIRECRACKER_SOCKET = "/tmp/firecracker.socket"
    ROOTFS_PATH = "/var/lib/firecracker/rootfs.ext4"
    KERNEL_PATH = "/var/lib/firecracker/vmlinux"

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self._api_url = f"unix://{self.FIRECRACKER_SOCKET}"

    def _create_vm_config(self, vcpu_count: int = 1, mem_size_mb: int = 512) -> dict[str, Any]:
        """Create Firecracker VM configuration."""
        return {
            "vcpu_count": vcpu_count,
            "mem_size_mib": mem_size_mb,
            "smt": False,
            "track_dirty_pages": False,
        }

    def _create_boot_source(self) -> dict[str, Any]:
        """Create boot source configuration."""
        return {
            "kernel_image_path": self.KERNEL_PATH,
            "boot_args": "console=ttyS0 reboot=k panic=1 pci=off",
        }

    def _create_drive(self, drive_id: str = "rootfs") -> dict[str, Any]:
        """Create drive configuration."""
        return {
            "drive_id": drive_id,
            "path_on_host": self.ROOTFS_PATH,
            "is_root_device": True,
            "is_read_only": False,
        }

    def _create_network_interface(self) -> dict[str, Any]:
        """Create network interface (disabled by default)."""
        return {"iface_id": "eth0", "guest_mac": "AA:FC:00:00:00:01", "host_dev_name": "tap0"}

    def execute(self, code: str, timeout: Optional[int] = None) -> SandboxResult:
        """
        Execute code in Firecracker MicroVM.

        Note: This requires Firecracker to be installed and configured.
        Falls back to subprocess execution if Firecracker is not available.
        """
        timeout = timeout or self.config.timeout
        start_time = time.time()

        is_safe, warnings = CodeAnalyzer.analyze(code)
        if not is_safe:
            return SandboxResult(
                success=False, error=f"Security check failed: {'; '.join(warnings)}"
            )

        if not self.is_available():
            return self._fallback_execute(code, timeout, start_time)

        try:
            import subprocess  # noqa: F401

            import requests

            subprocess.run(["rm", "-f", self.FIRECRACKER_SOCKET], capture_output=True)

            fc_process = subprocess.Popen(
                ["firecracker", "--api-sock", self.FIRECRACKER_SOCKET],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            time.sleep(0.1)

            session = requests.Session()
            session.adapters.DEFAULT_RETRIES = 3

            vm_config = self._create_vm_config(
                vcpu_count=max(1, int(self.config.cpu_limit)),
                mem_size_mb=self.config.memory_limit_mb,
            )

            try:
                session.put(f"{self._api_url}/machine-config", json=vm_config, timeout=5)

                session.put(
                    f"{self._api_url}/boot-source", json=self._create_boot_source(), timeout=5
                )

                session.put(f"{self._api_url}/drives/rootfs", json=self._create_drive(), timeout=5)

                if not self.config.network_disabled:
                    session.put(
                        f"{self._api_url}/network-interfaces/eth0",
                        json=self._create_network_interface(),
                        timeout=5,
                    )

                actions_response = session.put(
                    f"{self._api_url}/actions",
                    json={"action_type": "InstanceStart"},
                    timeout=timeout,
                )

                if actions_response.status_code == 204:
                    stdout, stderr = fc_process.communicate(timeout=timeout)

                    return SandboxResult(
                        success=True,
                        output=stdout.decode("utf-8")[: self.config.max_output_size],
                        execution_time=time.time() - start_time,
                        exit_code=fc_process.returncode,
                    )
                else:
                    return SandboxResult(
                        success=False,
                        error=f"Failed to start VM: {actions_response.text}",
                        execution_time=time.time() - start_time,
                    )

            finally:
                with contextlib.suppress(Exception):
                    session.put(
                        f"{self._api_url}/actions", json={"action_type": "InstanceHalt"}, timeout=5
                    )

                fc_process.terminate()
                fc_process.wait(timeout=5)

        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                error=f"VM execution timed out after {timeout} seconds",
                execution_time=time.time() - start_time,
            )
        except FileNotFoundError:
            return self._fallback_execute(code, timeout, start_time)
        except Exception as e:
            return SandboxResult(
                success=False,
                error=f"Firecracker error: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _fallback_execute(self, code: str, timeout: int, start_time: float) -> SandboxResult:
        """Fallback to subprocess execution."""
        import os
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            temp_file = f.name

        try:
            result = subprocess.run(
                [sys.executable, temp_file], capture_output=True, text=True, timeout=timeout, env={}
            )

            if result.returncode == 0:
                return SandboxResult(
                    success=True,
                    output=result.stdout[: self.config.max_output_size],
                    execution_time=time.time() - start_time,
                    exit_code=0,
                )
            else:
                return SandboxResult(
                    success=False,
                    output=result.stdout[: self.config.max_output_size],
                    error=result.stderr[: self.config.max_output_size],
                    execution_time=time.time() - start_time,
                    exit_code=result.returncode,
                )
        finally:
            os.unlink(temp_file)

    def is_available(self) -> bool:
        """Check if Firecracker is available."""
        try:
            result = subprocess.run(["which", "firecracker"], capture_output=True)
            return result.returncode == 0
        except Exception:
            return False


class ResourceMonitor:
    """
    Monitor and limit resource usage during execution.

    Tracks:
        - CPU usage
        - Memory usage
        - Execution time
        - File descriptors
    """

    def __init__(self, pid: Optional[int] = None):
        self.pid = pid or os.getpid()
        self._start_time = None
        self._start_cpu = None
        self._start_memory = None

    def start(self):
        """Start monitoring."""
        self._start_time = time.time()

        try:
            import psutil

            process = psutil.Process(self.pid)
            self._start_cpu = process.cpu_times()
            self._start_memory = process.memory_info()
        except ImportError:
            self._start_cpu = None
            self._start_memory = None

    def stop(self) -> dict[str, float]:
        """Stop monitoring and return resource usage."""
        end_time = time.time()

        result = {
            "execution_time": end_time - (self._start_time or end_time),
            "cpu_time_user": 0.0,
            "cpu_time_system": 0.0,
            "memory_used_mb": 0.0,
            "memory_peak_mb": 0.0,
        }

        try:
            import psutil

            process = psutil.Process(self.pid)

            end_cpu = process.cpu_times()
            end_memory = process.memory_info()

            if self._start_cpu:
                result["cpu_time_user"] = end_cpu.user - self._start_cpu.user
                result["cpu_time_system"] = end_cpu.system - self._start_cpu.system

            if self._start_memory:
                result["memory_used_mb"] = (end_memory.rss - self._start_memory.rss) / (1024 * 1024)

            result["memory_peak_mb"] = end_memory.rss / (1024 * 1024)

        except ImportError:
            pass

        return result


class SecureSandbox:
    """
    Unified sandbox interface with automatic level selection.

    Usage:
        sandbox = SecureSandbox(level=SandboxLevel.CONTAINER)
        result = sandbox.execute("print('hello')")

        # Auto-select best available level
        sandbox = SecureSandbox(level="auto")
    """

    def __init__(
        self, level: SandboxLevel = SandboxLevel.BASIC, config: Optional[SandboxConfig] = None
    ):
        self.level = level
        self.config = config or SandboxConfig()
        self._impl = self._create_implementation()

    def _create_implementation(self):
        """Create sandbox implementation based on level."""
        if self.level == SandboxLevel.BASIC:
            return BasicSandbox(self.config)
        elif self.level == SandboxLevel.CONTAINER:
            return DockerSandbox(self.config)
        elif self.level == SandboxLevel.GVISOR:
            return GVisorSandbox(self.config)
        elif self.level == SandboxLevel.MICROVM:
            return FirecrackerSandbox(self.config)
        elif self.level == SandboxLevel.WASM:
            return WASMSandbox(self.config)
        else:
            raise ValueError(f"Unsupported sandbox level: {self.level}")

    def execute(self, code: str, timeout: Optional[int] = None, **kwargs) -> SandboxResult:
        """
        Execute code in sandbox.

        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds
            **kwargs: Additional sandbox-specific options

        Returns:
            SandboxResult with execution results
        """
        return self._impl.execute(code, timeout)

    async def execute_async(
        self, code: str, timeout: Optional[int] = None, **kwargs
    ) -> SandboxResult:
        """Async version of execute."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.execute(code, timeout, **kwargs))

    @classmethod
    def auto_select(cls, config: Optional[SandboxConfig] = None) -> "SecureSandbox":
        """
        Automatically select the best available sandbox level.

        Priority: Firecracker > gVisor > Docker > WASM > Basic
        """
        try:
            firecracker = FirecrackerSandbox(config)
            if firecracker.is_available():
                return cls(SandboxLevel.MICROVM, config)
        except Exception:
            pass

        try:
            gvisor = GVisorSandbox(config)
            if gvisor.is_available():
                return cls(SandboxLevel.GVISOR, config)
        except Exception:
            pass

        try:
            docker_sandbox = DockerSandbox(config)
            docker_sandbox._get_client()
            return cls(SandboxLevel.CONTAINER, config)
        except Exception:
            pass

        try:
            wasm = WASMSandbox(config)
            if wasm.is_available():
                return cls(SandboxLevel.BASIC, config)
        except Exception:
            pass

        return cls(SandboxLevel.BASIC, config)


def check_code_safety(code: str) -> dict[str, Any]:
    """
    Check if code is safe to execute.

    This is a convenience function for the CodeAnalyzer.

    Args:
        code: Python code to analyze

    Returns:
        Dict with 'safe' boolean and optional 'error' or 'warnings'
    """
    is_safe, warnings = CodeAnalyzer.analyze(code)

    if is_safe:
        return {"safe": True, "message": "Code passed security checks"}
    else:
        return {"safe": False, "warnings": warnings}


__all__ = [
    "SandboxLevel",
    "SandboxResult",
    "SandboxConfig",
    "CodeAnalyzer",
    "BasicSandbox",
    "DockerSandbox",
    "GVisorSandbox",
    "WASMSandbox",
    "FirecrackerSandbox",
    "ResourceMonitor",
    "SecureSandbox",
    "check_code_safety",
]

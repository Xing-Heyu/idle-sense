"""
统一沙箱实现

整合多种隔离级别的沙箱：
- BasicSandbox: 基础进程隔离
- DockerSandbox: Docker容器隔离
- GVisorSandbox: gVisor增强隔离
- FirecrackerSandbox: 微虚拟机隔离
- WASMSandbox: WebAssembly沙箱
"""

import contextlib
import importlib
import logging
import os
import subprocess
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .security import CodeValidator


class IsolationLevel(Enum):
    """隔离级别"""

    BASIC = "basic"
    CONTAINER = "container"
    GVISOR = "gvisor"
    MICROVM = "microvm"
    WASM = "wasm"


@dataclass
class SandboxConfig:
    """沙箱配置"""

    timeout: int = 300
    memory_limit: int = 512
    cpu_limit: float = 1.0
    isolation_level: IsolationLevel = IsolationLevel.BASIC
    network_enabled: bool = False
    env_vars: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeout": self.timeout,
            "memory_limit": self.memory_limit,
            "cpu_limit": self.cpu_limit,
            "isolation_level": self.isolation_level.value,
            "network_enabled": self.network_enabled,
            "env_vars": self.env_vars,
        }


@dataclass
class ExecutionResult:
    """执行结果"""

    success: bool
    output: str = ""
    error: Optional[str] = None
    execution_time: float = 0.0
    memory_used: int = 0
    exit_code: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "memory_used": self.memory_used,
            "exit_code": self.exit_code,
        }


class BaseSandbox(ABC):
    """沙箱基类"""

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self.validator = CodeValidator()

    @abstractmethod
    def execute(self, code: str) -> ExecutionResult:
        """执行代码"""
        pass

    def validate_code(self, code: str) -> dict[str, Any]:
        """验证代码安全性"""
        return self.validator.check_code_safety(code)

    def _prepare_safe_globals(self) -> dict[str, Any]:
        """准备安全的全局命名空间"""
        safe_builtins = {
            "abs": abs,
            "max": max,
            "min": min,
            "sum": sum,
            "len": len,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "sorted": sorted,
            "reversed": reversed,
            "filter": filter,
            "map": map,
            "any": any,
            "all": all,
            "bool": bool,
            "int": int,
            "float": float,
            "str": str,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "print": print,
            "isinstance": isinstance,
            "type": type,
            "hasattr": hasattr,
            "getattr": getattr,
            "setattr": setattr,
            "repr": repr,
            "hash": hash,
            "id": id,
            "True": True,
            "False": False,
            "None": None,
        }

        safe_globals = {"__builtins__": safe_builtins}

        for module_name in self.validator.policy.allowed_modules:
            with contextlib.suppress(ImportError):
                safe_globals[module_name] = importlib.import_module(module_name)

        return safe_globals


class BasicSandbox(BaseSandbox):
    """
    基础沙箱

    使用subprocess进行进程隔离
    适用于低风险代码执行
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        super().__init__(config)
        self.config.isolation_level = IsolationLevel.BASIC

    def execute(self, code: str) -> ExecutionResult:
        start_time = time.time()

        safety_result = self.validate_code(code)
        if not safety_result["safe"]:
            return ExecutionResult(
                success=False, error=safety_result["error"], execution_time=time.time() - start_time
            )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            temp_file = f.name

        try:
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env.update(self.config.env_vars)

            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                env=env if not self.config.network_enabled else os.environ,
            )

            execution_time = time.time() - start_time

            if result.returncode == 0:
                return ExecutionResult(
                    success=True,
                    output=result.stdout.strip() or "执行完成（无输出）",
                    execution_time=execution_time,
                    exit_code=0,
                )
            else:
                return ExecutionResult(
                    success=False,
                    error=result.stderr.strip() or f"Exit code {result.returncode}",
                    execution_time=execution_time,
                    exit_code=result.returncode,
                )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error=f"执行超时（{self.config.timeout}秒）",
                execution_time=self.config.timeout,
            )
        except OSError as e:
            logging.error(f"[BasicSandbox] 系统错误: {e}")
            return ExecutionResult(
                success=False, error=f"系统错误: {str(e)}", execution_time=time.time() - start_time
            )
        except Exception as e:
            logging.exception("[BasicSandbox] 未预期的执行异常")
            return ExecutionResult(
                success=False, error=f"执行异常: {str(e)}", execution_time=time.time() - start_time
            )
        finally:
            with contextlib.suppress(BaseException):
                os.unlink(temp_file)


class DockerSandbox(BaseSandbox):
    """
    Docker沙箱

    使用Docker容器进行隔离
    提供更强的安全隔离
    """

    def __init__(self, config: Optional[SandboxConfig] = None, image: str = "python:3.11-slim"):
        super().__init__(config)
        self.config.isolation_level = IsolationLevel.CONTAINER
        self.image = image
        self._docker_available = self._check_docker()

    def _check_docker(self) -> bool:
        try:
            result = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    def execute(self, code: str) -> ExecutionResult:
        start_time = time.time()

        if not self._docker_available:
            return ExecutionResult(
                success=False,
                error="Docker不可用，请确保Docker已安装并运行",
                execution_time=time.time() - start_time,
            )

        safety_result = self.validate_code(code)
        if not safety_result["safe"]:
            return ExecutionResult(
                success=False, error=safety_result["error"], execution_time=time.time() - start_time
            )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            temp_file = f.name

        try:
            container_name = f"idle_sense_{os.getpid()}_{int(time.time())}"

            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "--name",
                container_name,
                "--memory",
                f"{self.config.memory_limit}m",
                "--cpus",
                str(self.config.cpu_limit),
                "-v",
                f"{temp_file}:/app/code.py:ro",
                self.image,
                "python",
                "/app/code.py",
            ]

            if not self.config.network_enabled:
                docker_cmd.insert(4, "--network=none")

            result = subprocess.run(
                docker_cmd, capture_output=True, text=True, timeout=self.config.timeout + 30
            )

            execution_time = time.time() - start_time

            if result.returncode == 0:
                return ExecutionResult(
                    success=True,
                    output=result.stdout.strip() or "执行完成（无输出）",
                    execution_time=execution_time,
                    exit_code=0,
                )
            else:
                return ExecutionResult(
                    success=False,
                    error=result.stderr.strip() or f"Container exit code {result.returncode}",
                    execution_time=execution_time,
                    exit_code=result.returncode,
                )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error=f"执行超时（{self.config.timeout}秒）",
                execution_time=self.config.timeout,
            )
        except OSError as e:
            logging.error(f"[DockerSandbox] 系统错误: {e}")
            return ExecutionResult(
                success=False, error=f"系统错误: {str(e)}", execution_time=time.time() - start_time
            )
        except Exception as e:
            logging.exception("[DockerSandbox] 未预期的执行异常")
            return ExecutionResult(
                success=False, error=f"执行异常: {str(e)}", execution_time=time.time() - start_time
            )
        finally:
            with contextlib.suppress(BaseException):
                os.unlink(temp_file)


class GVisorSandbox(DockerSandbox):
    """
    gVisor沙箱

    使用gVisor runsc运行时增强隔离
    提供更强的安全保护
    """

    def __init__(self, config: Optional[SandboxConfig] = None, image: str = "python:3.11-slim"):
        super().__init__(config, image)
        self.config.isolation_level = IsolationLevel.GVISOR
        self._gvisor_available = self._check_gvisor()

    def _check_gvisor(self) -> bool:
        try:
            result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=5)
            return "runsc" in result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    def execute(self, code: str) -> ExecutionResult:
        if not self._gvisor_available:
            return ExecutionResult(
                success=False, error="gVisor不可用，请确保已安装runsc运行时", execution_time=0
            )

        start_time = time.time()

        safety_result = self.validate_code(code)
        if not safety_result["safe"]:
            return ExecutionResult(
                success=False, error=safety_result["error"], execution_time=time.time() - start_time
            )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            temp_file = f.name

        try:
            container_name = f"idle_sense_gvisor_{os.getpid()}_{int(time.time())}"

            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "--runtime=runsc",
                "--name",
                container_name,
                "--memory",
                f"{self.config.memory_limit}m",
                "--cpus",
                str(self.config.cpu_limit),
                "-v",
                f"{temp_file}:/app/code.py:ro",
                self.image,
                "python",
                "/app/code.py",
            ]

            if not self.config.network_enabled:
                docker_cmd.insert(4, "--network=none")

            result = subprocess.run(
                docker_cmd, capture_output=True, text=True, timeout=self.config.timeout + 30
            )

            execution_time = time.time() - start_time

            if result.returncode == 0:
                return ExecutionResult(
                    success=True,
                    output=result.stdout.strip() or "执行完成（无输出）",
                    execution_time=execution_time,
                    exit_code=0,
                )
            else:
                return ExecutionResult(
                    success=False,
                    error=result.stderr.strip() or f"Container exit code {result.returncode}",
                    execution_time=execution_time,
                    exit_code=result.returncode,
                )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error=f"执行超时（{self.config.timeout}秒）",
                execution_time=self.config.timeout,
            )
        except OSError as e:
            logging.error(f"[GVisorSandbox] 系统错误: {e}")
            return ExecutionResult(
                success=False, error=f"系统错误: {str(e)}", execution_time=time.time() - start_time
            )
        except Exception as e:
            logging.exception("[GVisorSandbox] 未预期的执行异常")
            return ExecutionResult(
                success=False, error=f"执行异常: {str(e)}", execution_time=time.time() - start_time
            )
        finally:
            with contextlib.suppress(BaseException):
                os.unlink(temp_file)


class FirecrackerSandbox(BaseSandbox):
    """
    Firecracker微虚拟机沙箱

    使用Firecracker微虚拟机进行最强隔离
    适用于高风险代码执行
    """

    def __init__(
        self,
        config: Optional[SandboxConfig] = None,
        kernel_path: str = "/var/lib/firecracker/vmlinux",
        rootfs_path: str = "/var/lib/firecracker/rootfs.ext4",
    ):
        super().__init__(config)
        self.config.isolation_level = IsolationLevel.MICROVM
        self.kernel_path = kernel_path
        self.rootfs_path = rootfs_path
        self._firecracker_available = self._check_firecracker()

    def _check_firecracker(self) -> bool:
        try:
            result = subprocess.run(["firecracker", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    def _create_vm_config(self, socket_path: str, vm_id: str) -> dict:
        return {
            "boot-source": {
                "kernel_image_path": self.kernel_path,
                "boot_args": "console=ttyS0 reboot=k panic=1 pci=off init=/sbin/init",
            },
            "drives": [
                {
                    "drive_id": "rootfs",
                    "path_on_host": self.rootfs_path,
                    "is_root_device": True,
                    "is_read_only": False,
                }
            ],
            "machine-config": {
                "vcpu_count": 1,
                "mem_size_mib": self.config.memory_limit,
                "ht_enabled": False,
            },
            "network-interfaces": (
                []
                if not self.config.network_enabled
                else [
                    {
                        "iface_id": "eth0",
                        "guest_mac": "AA:FC:00:00:00:01",
                        "host_dev_name": f"tap{vm_id}",
                    }
                ]
            ),
        }

    def execute(self, code: str) -> ExecutionResult:
        start_time = time.time()

        if not self._firecracker_available:
            return ExecutionResult(
                success=False,
                error="Firecracker不可用，请确保已安装Firecracker并配置kernel/rootfs",
                execution_time=time.time() - start_time,
            )

        safety_result = self.validate_code(code)
        if not safety_result["safe"]:
            return ExecutionResult(
                success=False, error=safety_result["error"], execution_time=time.time() - start_time
            )

        if not os.path.exists(self.kernel_path):
            return ExecutionResult(
                success=False,
                error=f"Kernel镜像不存在: {self.kernel_path}",
                execution_time=time.time() - start_time,
            )

        if not os.path.exists(self.rootfs_path):
            return ExecutionResult(
                success=False,
                error=f"RootFS镜像不存在: {self.rootfs_path}",
                execution_time=time.time() - start_time,
            )

        vm_id = None
        socket_path = None
        code_file = None
        config_file = None
        fc_process = None

        try:
            vm_id = f"idle_{os.getpid()}_{int(time.time())}"
            socket_path = f"/tmp/firecracker_{vm_id}.sock"
            code_file = f"/tmp/code_{vm_id}.py"

            with open(code_file, "w", encoding="utf-8") as f:
                f.write(code)

            vm_config = self._create_vm_config(socket_path, vm_id)

            config_file = f"/tmp/firecracker_config_{vm_id}.json"
            with open(config_file, "w", encoding="utf-8") as f:
                import json

                json.dump(vm_config, f)

            fc_process = subprocess.Popen(
                ["firecracker", "--api-sock", socket_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            time.sleep(0.5)

            with contextlib.suppress(Exception):
                subprocess.run(
                    [
                        "curl",
                        "--unix-socket",
                        socket_path,
                        "-X",
                        "PUT",
                        "http://localhost/machine-config",
                        "-H",
                        "Content-Type: application/json",
                        "-d",
                        json.dumps(vm_config["machine-config"]),
                    ],
                    capture_output=True,
                    timeout=5,
                )

            fc_process.wait(timeout=self.config.timeout)

            output = (
                fc_process.stdout.read().decode("utf-8", errors="replace")
                if fc_process.stdout
                else ""
            )
            error = (
                fc_process.stderr.read().decode("utf-8", errors="replace")
                if fc_process.stderr
                else ""
            )

            execution_time = time.time() - start_time

            if fc_process.returncode == 0:
                return ExecutionResult(
                    success=True,
                    output=output.strip() or "执行完成（无输出）",
                    execution_time=execution_time,
                    exit_code=0,
                )
            else:
                return ExecutionResult(
                    success=False,
                    error=error.strip() or f"VM exit code {fc_process.returncode}",
                    execution_time=execution_time,
                    exit_code=fc_process.returncode,
                )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error=f"执行超时（{self.config.timeout}秒）",
                execution_time=self.config.timeout,
            )
        except OSError as e:
            logging.error(f"[FirecrackerSandbox] 系统错误: {e}")
            return ExecutionResult(
                success=False, error=f"系统错误: {str(e)}", execution_time=time.time() - start_time
            )
        except Exception as e:
            logging.exception("[FirecrackerSandbox] 未预期的执行异常")
            return ExecutionResult(
                success=False, error=f"执行异常: {str(e)}", execution_time=time.time() - start_time
            )
        finally:
            if fc_process:
                with contextlib.suppress(Exception):
                    fc_process.terminate()
                    fc_process.wait()

            for path in [code_file, config_file, socket_path]:
                if path and os.path.exists(path):
                    with contextlib.suppress(Exception):
                        os.unlink(path)


class WASMSandbox(BaseSandbox):
    """
    WebAssembly沙箱

    使用WASM运行时进行隔离
    提供轻量级的安全执行环境
    """

    def __init__(self, config: Optional[SandboxConfig] = None, runtime: str = "wasmer"):
        super().__init__(config)
        self.config.isolation_level = IsolationLevel.WASM
        self.runtime = runtime
        self._wasm_available = self._check_wasm()
        self._runtime_module = None
        self._code_validator = CodeValidator()
        self._logger = logging.getLogger(__name__)

    def _check_wasm(self) -> bool:
        if self.runtime == "wasmer":
            try:
                import wasmer  # noqa: F401

                return True
            except ImportError:
                pass
        elif self.runtime == "wasmtime":
            try:
                import wasmtime  # noqa: F401

                return True
            except ImportError:
                pass

        try:
            result = subprocess.run([self.runtime, "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    def _compile_python_to_wasm(self, code: str) -> Optional[bytes]:
        try:
            try:
                import pyodide  # noqa: F401

                return self._compile_with_pyodide(code)
            except ImportError:
                pass

            try:
                import rustpython  # noqa: F401

                return self._compile_with_rustpython(code)
            except ImportError:
                pass

            return self._create_wat_wrapper(code)
        except Exception:
            return None

    def _create_wat_wrapper(self, code: str) -> bytes:
        import base64

        encoded_code = base64.b64encode(code.encode("utf-8")).decode("ascii")

        wat_code = f"""
(module
  (import "env" "execute_python" (func $execute_python (param i32 i32) (result i32)))
  (memory (export "memory") 1)
  (data (i32.const 0) "{encoded_code}")
  (func (export "_start")
    (drop (call $execute_python (i32.const 0) (i32.const {len(encoded_code)})))
  )
)
"""
        try:
            result = subprocess.run(
                ["wat2wasm", "-", "-o", "-"],
                input=wat_code.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

        return None

    def _compile_with_pyodide(self, code: str) -> Optional[bytes]:
        """
        使用Pyodide将Python代码编译为WASM

        注意：此功能需要完整安装Pyodide环境，包括：
        - pyodide Python包
        - Pyodide运行时环境
        - Emscripten工具链

        当前为占位实现，返回None以触发fallback到其他编译方法。

        Args:
            code: Python源代码

        Returns:
            编译后的WASM字节码，当前实现返回None

        Future Implementation:
            1. 初始化Pyodide环境
            2. 使用Pyodide的Python-to-WASM编译器
            3. 返回编译后的WASM模块
        """
        self._logger.debug(f"[WASM编译] Pyodide编译方法被调用 - 代码长度: {len(code)} 字符")
        self._logger.warning("[WASM编译] Pyodide编译功能尚未实现，将使用fallback方法")
        return None

    def _compile_with_rustpython(self, code: str) -> Optional[bytes]:
        """
        使用RustPython将Python代码编译为WASM

        注意：此功能需要：
        - rustpython Python包
        - RustPython WASM运行时

        当前为占位实现，返回None以触发fallback到其他编译方法。

        Args:
            code: Python源代码

        Returns:
            编译后的WASM字节码，当前实现返回None

        Future Implementation:
            1. 初始化RustPython环境
            2. 使用RustPython的WASM后端
            3. 返回编译后的WASM模块
        """
        self._logger.debug(f"[WASM编译] RustPython编译方法被调用 - 代码长度: {len(code)} 字符")
        self._logger.warning("[WASM编译] RustPython编译功能尚未实现，将使用fallback方法")
        return None

    def execute(self, code: str) -> ExecutionResult:
        start_time = time.time()

        if not self._wasm_available:
            return ExecutionResult(
                success=False,
                error="WASM运行时不可用，请安装wasmer或wasmtime Python包",
                execution_time=time.time() - start_time,
            )

        safety_result = self.validate_code(code)
        if not safety_result["safe"]:
            return ExecutionResult(
                success=False, error=safety_result["error"], execution_time=time.time() - start_time
            )

        try:
            if self.runtime == "wasmer":
                return self._execute_with_wasmer(code, start_time)
            elif self.runtime == "wasmtime":
                return self._execute_with_wasmtime(code, start_time)
            else:
                return self._execute_with_cli(code, start_time)

        except ImportError as e:
            logging.error(f"[WASMSandbox] 运行时未安装: {e}")
            return ExecutionResult(
                success=False, error=f"WASM运行时未安装: {str(e)}", execution_time=time.time() - start_time
            )
        except OSError as e:
            logging.error(f"[WASMSandbox] 系统错误: {e}")
            return ExecutionResult(
                success=False, error=f"系统错误: {str(e)}", execution_time=time.time() - start_time
            )
        except Exception as e:
            logging.exception("[WASMSandbox] 未预期的执行异常")
            return ExecutionResult(
                success=False, error=f"执行异常: {str(e)}", execution_time=time.time() - start_time
            )

    def _safe_execute_python(self, python_code: str) -> tuple[bool, str]:
        """
        安全执行Python代码（AST白名单验证 + 进程隔离）

        使用CodeValidator进行AST级别的安全验证，
        然后通过subprocess在隔离进程中执行代码。

        Args:
            python_code: 要执行的Python代码

        Returns:
            tuple: (是否成功, 结果或错误信息)
        """
        self._logger.warning(
            f"[安全审计] 代码执行尝试 - 长度: {len(python_code)} 字符, "
            f"时间戳: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        validation_result = self._code_validator.validate(python_code)

        if not validation_result.is_safe:
            error_msg = f"安全验证失败: {'; '.join(validation_result.errors)}"
            self._logger.error(f"[安全警告] 代码执行被阻止 - 原因: {error_msg}")
            return False, error_msg

        if validation_result.warnings:
            self._logger.warning(
                f"[安全提示] 代码包含潜在风险: {'; '.join(validation_result.warnings)}"
            )

        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(python_code)
            temp_file = f.name

        try:
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env.pop("PYTHONHOME", None)
            env["__PYTHON_SANDBOX"] = "1"

            result = subprocess.run(
                [sys.executable, "-S", temp_file],
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                env=env,
                cwd=tempfile.gettempdir(),
            )

            if result.returncode == 0:
                output = result.stdout.strip() or "OK"
                self._logger.info(
                    f"[安全审计] 代码执行成功 - 安全级别: {validation_result.security_level.value}"
                )
                return True, output
            else:
                error_msg = result.stderr.strip() or f"Exit code {result.returncode}"
                self._logger.error(f"[安全审计] 代码执行异常: {error_msg}")
                return False, error_msg

        except subprocess.TimeoutExpired:
            error_msg = f"执行超时（{self.config.timeout}秒）"
            self._logger.error(f"[安全审计] 代码执行超时: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"执行错误: {str(e)}"
            self._logger.error(f"[安全审计] 代码执行异常: {error_msg}")
            return False, error_msg
        finally:
            with contextlib.suppress(BaseException):
                os.unlink(temp_file)

    def _execute_with_wasmer(self, code: str, start_time: float) -> ExecutionResult:
        try:
            import wasmer
            from wasmer import Instance, Module, Store  # noqa: F401

            wasm_bytes = self._compile_python_to_wasm(code)
            if wasm_bytes is None:
                return ExecutionResult(
                    success=False,
                    error="无法将Python代码编译为WASM，请使用简单的数学运算或安装pyodide",
                    execution_time=time.time() - start_time,
                )

            store = Store()
            module = Module(store, wasm_bytes)

            output_buffer = []

            def env_execute_python(offset: int, length: int) -> int:
                memory = instance.exports.memory
                data = memory.data_ptr()[offset : offset + length]
                try:
                    decoded = bytes(data).decode("utf-8")
                    import base64

                    python_code = base64.b64decode(decoded).decode("utf-8")
                    success, result = self._safe_execute_python(python_code)
                    output_buffer.append(result)
                    return 0 if success else 1
                except Exception as e:
                    output_buffer.append(str(e))
                    return 1

            import_instance = wasmer.ImportObject()
            import_instance.register(
                "env", {"execute_python": wasmer.Function(store, env_execute_python)}
            )

            instance = Instance(module, import_instance)
            instance.exports._start()

            return ExecutionResult(
                success=True,
                output="\n".join(output_buffer) or "执行完成（无输出）",
                execution_time=time.time() - start_time,
                exit_code=0,
            )

        except ImportError:
            return ExecutionResult(
                success=False,
                error="wasmer Python包未安装，请运行: pip install wasmer",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Wasmer执行错误: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _execute_with_wasmtime(self, code: str, start_time: float) -> ExecutionResult:
        try:
            import wasmtime

            wasm_bytes = self._compile_python_to_wasm(code)
            if wasm_bytes is None:
                return ExecutionResult(
                    success=False,
                    error="无法将Python代码编译为WASM",
                    execution_time=time.time() - start_time,
                )

            engine = wasmtime.Engine()
            store = wasmtime.Store(engine)
            module = wasmtime.Module(engine, wasm_bytes)

            output_buffer = []

            def execute_python(caller, offset: int, length: int) -> int:
                memory = caller.get_export("memory").unwrap_memory()
                data = memory.data_ptr(store)[offset : offset + length]
                try:
                    decoded = bytes(data).decode("utf-8")
                    import base64

                    python_code = base64.b64decode(decoded).decode("utf-8")
                    success, result = self._safe_execute_python(python_code)
                    output_buffer.append(result)
                    return 0 if success else 1
                except Exception as e:
                    output_buffer.append(str(e))
                    return 1

            linker = wasmtime.Linker(engine)
            linker.define(store, wasmtime.wasi.WasiInstance(store, "env", execute_python))

            instance = linker.instantiate(store, module)
            instance.exports(store)["_start"](store)

            return ExecutionResult(
                success=True,
                output="\n".join(output_buffer) or "执行完成（无输出）",
                execution_time=time.time() - start_time,
                exit_code=0,
            )

        except ImportError:
            return ExecutionResult(
                success=False,
                error="wasmtime Python包未安装，请运行: pip install wasmtime",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Wasmtime执行错误: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _execute_with_cli(self, code: str, start_time: float) -> ExecutionResult:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            temp_file = f.name

        try:
            result = subprocess.run(
                [self.runtime, "run", temp_file],
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
            )

            execution_time = time.time() - start_time

            if result.returncode == 0:
                return ExecutionResult(
                    success=True,
                    output=result.stdout.strip() or "执行完成（无输出）",
                    execution_time=execution_time,
                    exit_code=0,
                )
            else:
                return ExecutionResult(
                    success=False,
                    error=result.stderr.strip() or f"Exit code {result.returncode}",
                    execution_time=execution_time,
                    exit_code=result.returncode,
                )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error=f"执行超时（{self.config.timeout}秒）",
                execution_time=self.config.timeout,
            )
        finally:
            with contextlib.suppress(BaseException):
                os.unlink(temp_file)


class SandboxFactory:
    """沙箱工厂"""

    _sandboxes = {
        IsolationLevel.BASIC: BasicSandbox,
        IsolationLevel.CONTAINER: DockerSandbox,
        IsolationLevel.GVISOR: GVisorSandbox,
        IsolationLevel.MICROVM: FirecrackerSandbox,
        IsolationLevel.WASM: WASMSandbox,
    }

    @classmethod
    def create(cls, level: IsolationLevel, config: Optional[SandboxConfig] = None) -> BaseSandbox:
        """创建指定级别的沙箱"""
        sandbox_class = cls._sandboxes.get(level, BasicSandbox)
        return sandbox_class(config)

    @classmethod
    def get_available_levels(cls) -> list[IsolationLevel]:
        """获取可用的隔离级别"""
        available = []

        BasicSandbox()
        if True:
            available.append(IsolationLevel.BASIC)

        docker = DockerSandbox()
        if docker._docker_available:
            available.append(IsolationLevel.CONTAINER)

        gvisor = GVisorSandbox()
        if gvisor._gvisor_available:
            available.append(IsolationLevel.GVISOR)

        firecracker = FirecrackerSandbox()
        if firecracker._firecracker_available:
            available.append(IsolationLevel.MICROVM)

        wasm = WASMSandbox()
        if wasm._wasm_available:
            available.append(IsolationLevel.WASM)

        return available

    @classmethod
    def get_best_available(cls, config: Optional[SandboxConfig] = None) -> BaseSandbox:
        """获取最佳可用沙箱"""
        levels = [
            IsolationLevel.MICROVM,
            IsolationLevel.GVISOR,
            IsolationLevel.CONTAINER,
            IsolationLevel.BASIC,
        ]

        available = cls.get_available_levels()

        for level in levels:
            if level in available:
                return cls.create(level, config)

        return cls.create(IsolationLevel.BASIC, config)


__all__ = [
    "IsolationLevel",
    "SandboxConfig",
    "ExecutionResult",
    "BaseSandbox",
    "BasicSandbox",
    "DockerSandbox",
    "GVisorSandbox",
    "FirecrackerSandbox",
    "WASMSandbox",
    "SandboxFactory",
]

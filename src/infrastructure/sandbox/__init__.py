"""
统一沙箱模块

整合 legacy/sandbox 和 legacy/sandbox_v2 的功能：
- 基础沙箱 (BasicSandbox)
- Docker沙箱 (DockerSandbox)
- gVisor沙箱 (GVisorSandbox)
- Firecracker微虚拟机 (FirecrackerSandbox)
- WASM沙箱 (WASMSandbox)
"""

from .sandbox import (
    BaseSandbox,
    BasicSandbox,
    DockerSandbox,
    ExecutionResult,
    FirecrackerSandbox,
    GVisorSandbox,
    IsolationLevel,
    SandboxConfig,
    SandboxFactory,
    WASMSandbox,
)
from .security import CodeValidator, SecurityPolicy

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
    "SecurityPolicy",
    "CodeValidator",
]

"""
统一沙箱模块测试
"""

import pytest

from src.infrastructure.sandbox import (
    BaseSandbox,
    BasicSandbox,
    DockerSandbox,
    ExecutionResult,
    IsolationLevel,
    SandboxConfig,
    SandboxFactory,
)
from src.infrastructure.sandbox.security import (
    CodeValidator,
    SecurityPolicy,
)


class TestSecurityPolicy:
    """安全策略测试"""

    def test_default_policy(self):
        """测试默认策略"""
        policy = SecurityPolicy()

        assert 'math' in policy.allowed_modules
        assert 'os' not in policy.allowed_modules
        assert 'eval' in policy.dangerous_builtins
        assert '__class__' in policy.dangerous_attributes

    def test_policy_to_dict(self):
        """测试策略序列化"""
        policy = SecurityPolicy()
        data = policy.to_dict()

        assert "allowed_modules" in data
        assert "dangerous_builtins" in data
        assert "max_code_length" in data


class TestCodeValidator:
    """代码验证器测试"""

    def test_safe_code(self):
        """测试安全代码"""
        validator = CodeValidator()

        safe_code = """
import math
result = math.sqrt(16)
print(result)
"""

        result = validator.validate(safe_code)

        assert result.is_safe is True
        assert len(result.errors) == 0

    def test_dangerous_import(self):
        """测试危险导入"""
        validator = CodeValidator()

        dangerous_code = """
import os
os.system('rm -rf /')
"""

        result = validator.validate(dangerous_code)

        assert result.is_safe is False
        assert any("os" in e for e in result.errors)

    def test_dangerous_builtin(self):
        """测试危险内置函数"""
        validator = CodeValidator()

        dangerous_code = """
result = eval("1 + 1")
"""

        result = validator.validate(dangerous_code)

        assert result.is_safe is False
        assert any("eval" in e for e in result.errors)

    def test_dangerous_attribute(self):
        """测试危险属性访问"""
        validator = CodeValidator()

        dangerous_code = """
obj.__class__.__bases__
"""

        result = validator.validate(dangerous_code)

        assert result.is_safe is False
        assert any("__class__" in e for e in result.errors)

    def test_code_too_long(self):
        """测试代码超长"""
        policy = SecurityPolicy(max_code_length=100)
        validator = CodeValidator(policy)

        long_code = "x = 1\n" * 100

        result = validator.validate(long_code)

        assert result.is_safe is False
        assert any("长度" in e for e in result.errors)

    def test_check_code_safety_compatibility(self):
        """测试兼容旧接口"""
        validator = CodeValidator()

        result = validator.check_code_safety("import math\nprint(math.pi)")

        assert result['safe'] is True
        assert result['error'] is None


class TestSandboxConfig:
    """沙箱配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = SandboxConfig()

        assert config.timeout == 300
        assert config.memory_limit == 512
        assert config.cpu_limit == 1.0
        assert config.isolation_level == IsolationLevel.BASIC
        assert config.network_enabled is False

    def test_custom_config(self):
        """测试自定义配置"""
        config = SandboxConfig(
            timeout=600,
            memory_limit=1024,
            cpu_limit=2.0,
            isolation_level=IsolationLevel.CONTAINER,
            network_enabled=True
        )

        assert config.timeout == 600
        assert config.memory_limit == 1024
        assert config.cpu_limit == 2.0
        assert config.isolation_level == IsolationLevel.CONTAINER
        assert config.network_enabled is True

    def test_config_to_dict(self):
        """测试配置序列化"""
        config = SandboxConfig()
        data = config.to_dict()

        assert data["timeout"] == 300
        assert data["isolation_level"] == "basic"


class TestExecutionResult:
    """执行结果测试"""

    def test_success_result(self):
        """测试成功结果"""
        result = ExecutionResult(
            success=True,
            output="Hello, World!",
            execution_time=0.5
        )

        assert result.success is True
        assert result.output == "Hello, World!"
        assert result.error is None

    def test_failure_result(self):
        """测试失败结果"""
        result = ExecutionResult(
            success=False,
            error="执行超时",
            execution_time=300
        )

        assert result.success is False
        assert result.error == "执行超时"
        assert result.output == ""

    def test_result_to_dict(self):
        """测试结果序列化"""
        result = ExecutionResult(
            success=True,
            output="test",
            execution_time=1.0,
            exit_code=0
        )

        data = result.to_dict()

        assert data["success"] is True
        assert data["output"] == "test"
        assert data["exit_code"] == 0


class TestBasicSandbox:
    """基础沙箱测试"""

    def test_sandbox_initialization(self):
        """测试沙箱初始化"""
        sandbox = BasicSandbox()

        assert sandbox.config.isolation_level == IsolationLevel.BASIC
        assert sandbox.validator is not None

    def test_validate_code(self):
        """测试代码验证"""
        sandbox = BasicSandbox()

        result = sandbox.validate_code("import math\nprint(math.pi)")

        assert result['safe'] is True

    def test_execute_safe_code(self):
        """测试执行安全代码"""
        sandbox = BasicSandbox()

        code = """
import math
print(f"Pi is approximately {math.pi:.2f}")
"""

        result = sandbox.execute(code)

        assert result.success is True
        assert "Pi" in result.output or "3.14" in result.output

    def test_execute_dangerous_code(self):
        """测试执行危险代码"""
        sandbox = BasicSandbox()

        code = """
import os
print(os.getcwd())
"""

        result = sandbox.execute(code)

        assert result.success is False
        assert "禁止导入模块" in result.error

    def test_execute_with_custom_config(self):
        """测试自定义配置执行"""
        config = SandboxConfig(timeout=10, memory_limit=256)
        sandbox = BasicSandbox(config)

        code = "print('hello')"

        result = sandbox.execute(code)

        assert result.success is True


class TestDockerSandbox:
    """Docker沙箱测试"""

    def test_sandbox_initialization(self):
        """测试沙箱初始化"""
        sandbox = DockerSandbox()

        assert sandbox.config.isolation_level == IsolationLevel.CONTAINER
        assert sandbox.image == "python:3.11-slim"

    def test_docker_unavailable(self):
        """测试Docker不可用时的处理"""
        sandbox = DockerSandbox()

        if not sandbox._docker_available:
            code = "print('hello')"
            result = sandbox.execute(code)

            assert result.success is False
            assert "Docker不可用" in result.error


class TestSandboxFactory:
    """沙箱工厂测试"""

    def test_create_basic_sandbox(self):
        """测试创建基础沙箱"""
        sandbox = SandboxFactory.create(IsolationLevel.BASIC)

        assert isinstance(sandbox, BasicSandbox)
        assert sandbox.config.isolation_level == IsolationLevel.BASIC

    def test_create_with_config(self):
        """测试带配置创建沙箱"""
        config = SandboxConfig(timeout=600)
        sandbox = SandboxFactory.create(IsolationLevel.BASIC, config)

        assert sandbox.config.timeout == 600

    def test_get_available_levels(self):
        """测试获取可用级别"""
        levels = SandboxFactory.get_available_levels()

        assert IsolationLevel.BASIC in levels

    def test_get_best_available(self):
        """测试获取最佳可用沙箱"""
        sandbox = SandboxFactory.get_best_available()

        assert sandbox is not None
        assert isinstance(sandbox, BaseSandbox)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

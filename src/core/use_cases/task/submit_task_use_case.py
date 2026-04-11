"""
提交任务用例

使用示例：
    from src.core.use_cases.task import SubmitTaskUseCase, SubmitTaskRequest

    use_case = SubmitTaskUseCase(task_repository, scheduler_service)
    response = use_case.execute(SubmitTaskRequest(
        code="print('hello')",
        timeout=300,
        cpu=1.0,
        memory=512
    ))

    if response.success:
        print(f"任务提交成功: {response.task_id}")
"""

from dataclasses import dataclass
import logging
import re
from typing import Optional

from src.core.entities import TaskFactory
from src.core.interfaces.repositories import ITaskRepository
from src.core.interfaces.services import ISchedulerService

logger = logging.getLogger(__name__)

FALLBACK_DANGEROUS_PATTERNS = [
    r"__import__\s*\(",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"os\.system\s*\(",
    r"os\.popen\s*\(",
    r"subprocess\.",
    r"pickle\.loads?\s*\(",
    r"marshal\.loads?\s*\(",
    r"importlib\.",
    r"__builtins__",
    r"__globals__",
    r"__code__",
    r"__class__",
    r"__base__",
    r"__subclasses__",
    r"globals\s*\(",
    r"locals\s*\(",
    r"compile\s*\(",
]


@dataclass
class SubmitTaskRequest:
    """提交任务请求"""

    code: str
    user_id: Optional[str] = None
    timeout: int = 300
    cpu: float = 1.0
    memory: int = 512


@dataclass
class SubmitTaskResponse:
    """提交任务响应"""

    success: bool
    task_id: str = ""
    message: str = ""
    errors: list[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class SubmitTaskUseCase:
    """提交任务用例"""

    MAX_CODE_LENGTH = 100000
    MAX_TIMEOUT = 3600
    MIN_TIMEOUT = 1
    MAX_CPU = 16.0
    MIN_CPU = 0.1
    MAX_MEMORY = 65536
    MIN_MEMORY = 64

    def __init__(self, task_repository: ITaskRepository, scheduler_service: ISchedulerService):
        """
        初始化提交任务用例

        Args:
            task_repository: 任务仓储
            scheduler_service: 调度器服务
        """
        self._task_repository = task_repository
        self._scheduler_service = scheduler_service
        self._compiled_fallback_patterns = [
            re.compile(pattern) for pattern in FALLBACK_DANGEROUS_PATTERNS
        ]

    def _fallback_code_validation(self, code: str) -> list[str]:
        """
        备用代码安全验证（当 InputValidator 不可用时）

        Args:
            code: 要验证的代码

        Returns:
            错误列表
        """
        errors = []
        for pattern in self._compiled_fallback_patterns:
            if pattern.search(code):
                errors.append(f"检测到危险代码模式: {pattern.pattern}")
        return errors

    def _validate_request(self, request: SubmitTaskRequest) -> tuple[bool, list[str]]:
        """
        验证请求参数

        Args:
            request: 提交任务请求

        Returns:
            (是否有效, 错误列表)
        """
        errors = []

        if not request.code or not request.code.strip():
            errors.append("代码不能为空")
        elif len(request.code) > self.MAX_CODE_LENGTH:
            errors.append(f"代码长度超过限制 ({len(request.code)} > {self.MAX_CODE_LENGTH})")

        if request.timeout < self.MIN_TIMEOUT:
            errors.append(f"超时时间不能小于 {self.MIN_TIMEOUT} 秒")
        elif request.timeout > self.MAX_TIMEOUT:
            errors.append(f"超时时间不能超过 {self.MAX_TIMEOUT} 秒")

        if request.cpu < self.MIN_CPU:
            errors.append(f"CPU 请求数不能小于 {self.MIN_CPU}")
        elif request.cpu > self.MAX_CPU:
            errors.append(f"CPU 请求数不能超过 {self.MAX_CPU}")

        if request.memory < self.MIN_MEMORY:
            errors.append(f"内存请求不能小于 {self.MIN_MEMORY} MB")
        elif request.memory > self.MAX_MEMORY:
            errors.append(f"内存请求不能超过 {self.MAX_MEMORY} MB")

        try:
            from src.infrastructure.security.validators import InputValidator
            validator = InputValidator()
            code_validation = validator.validate_code(request.code)
            if not code_validation.valid:
                errors.extend(code_validation.errors)
        except ImportError as e:
            logger.warning(f"InputValidator 模块导入失败，使用备用验证: {e}")
            fallback_errors = self._fallback_code_validation(request.code)
            if fallback_errors:
                errors.extend(fallback_errors)
                logger.warning(f"备用验证检测到问题: {fallback_errors}")
        except Exception as e:
            logger.error(f"代码安全验证异常: {e}")
            errors.append(f"代码安全验证失败: {str(e)}")

        return len(errors) == 0, errors

    def execute(self, request: SubmitTaskRequest) -> SubmitTaskResponse:
        """
        执行提交任务

        Args:
            request: 提交任务请求

        Returns:
            提交任务响应
        """
        is_valid, errors = self._validate_request(request)
        if not is_valid:
            return SubmitTaskResponse(
                success=False,
                message="输入验证失败",
                errors=errors,
            )

        task = TaskFactory.create(
            code=request.code,
            user_id=request.user_id,
            timeout=request.timeout,
            cpu=request.cpu,
            memory=request.memory,
        )

        scheduler_result = self._scheduler_service.submit_task(
            code=task.code,
            timeout=task.timeout,
            cpu=task.cpu_request,
            memory=task.memory_request,
            user_id=task.user_id,
        )

        if not scheduler_result[0]:
            return SubmitTaskResponse(
                success=False,
                message=f"提交到调度器失败: {scheduler_result[1].get('error', '未知错误')}",
            )

        task.task_id = scheduler_result[1].get("task_id", task.task_id)
        self._task_repository.save(task)

        return SubmitTaskResponse(success=True, task_id=task.task_id, message="任务提交成功")


__all__ = ["SubmitTaskUseCase", "SubmitTaskRequest", "SubmitTaskResponse"]

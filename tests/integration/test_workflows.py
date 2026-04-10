"""
集成测试 - 模块协作测试

测试多个模块之间的协作
"""

import shutil
import tempfile
from unittest.mock import Mock

import pytest

from src.core.use_cases.auth.login_use_case import LoginRequest, LoginUseCase
from src.core.use_cases.auth.register_use_case import RegisterRequest, RegisterUseCase
from src.core.use_cases.task.submit_task_use_case import SubmitTaskRequest, SubmitTaskUseCase
from src.infrastructure.external import SchedulerClient
from src.infrastructure.repositories import FileUserRepository, InMemoryTaskRepository


class TestUserWorkflow:
    """用户工作流集成测试"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.user_repo = FileUserRepository(users_dir=self.temp_dir)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_register_then_login_workflow(self):
        """测试注册后登录的工作流"""
        register_use_case = RegisterUseCase(self.user_repo)

        register_response = register_use_case.execute(
            RegisterRequest(username="testuser", folder_location="project")
        )

        assert register_response.success is True
        assert register_response.user.username == "testuser"

        login_use_case = LoginUseCase(self.user_repo)
        login_response = login_use_case.execute(LoginRequest(username="testuser"))

        assert login_response.success is True
        assert login_response.user.username == "testuser"
        assert login_response.user.last_login is not None

    def test_register_duplicate_username(self):
        """测试重复用户名注册"""
        register_use_case = RegisterUseCase(self.user_repo)

        register_use_case.execute(RegisterRequest(username="testuser"))
        register_response = register_use_case.execute(RegisterRequest(username="testuser"))

        assert register_response.success is True
        assert register_response.user.username != "testuser"


class TestTaskWorkflow:
    """任务工作流集成测试"""

    def setup_method(self):
        self.task_repo = InMemoryTaskRepository()
        self.scheduler = Mock(spec=SchedulerClient)

    def test_submit_task_workflow(self):
        """测试提交任务工作流"""
        self.scheduler.submit_task.return_value = (True, {"task_id": "task_123"})

        use_case = SubmitTaskUseCase(self.task_repo, self.scheduler)

        response = use_case.execute(
            SubmitTaskRequest(
                code="print('hello')", timeout=300, cpu=1.0, memory=512, user_id="user_001"
            )
        )

        assert response.success is True
        assert response.task_id == "task_123"

        saved_task = self.task_repo.get_by_id("task_123")
        assert saved_task is not None
        assert saved_task.code == "print('hello')"

    def test_submit_task_scheduler_failure(self):
        """测试调度器失败时的工作流"""
        self.scheduler.submit_task.return_value = (False, {"error": "Scheduler offline"})

        use_case = SubmitTaskUseCase(self.task_repo, self.scheduler)

        response = use_case.execute(SubmitTaskRequest(code="print('hello')"))

        assert response.success is False
        assert "失败" in response.message


class TestFullWorkflow:
    """完整工作流集成测试"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.user_repo = FileUserRepository(users_dir=self.temp_dir)
        self.task_repo = InMemoryTaskRepository()
        self.scheduler = Mock(spec=SchedulerClient)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_complete_user_task_workflow(self):
        """测试完整的用户任务工作流"""
        # 1. 注册用户
        register_use_case = RegisterUseCase(self.user_repo)
        register_response = register_use_case.execute(
            RegisterRequest(username="developer", folder_location="project")
        )
        assert register_response.success is True
        user_id = register_response.user.user_id

        # 2. 登录用户
        login_use_case = LoginUseCase(self.user_repo)
        login_response = login_use_case.execute(LoginRequest(username="developer"))
        assert login_response.success is True

        # 3. 提交任务
        self.scheduler.submit_task.return_value = (True, {"task_id": "task_dev_001"})

        submit_use_case = SubmitTaskUseCase(self.task_repo, self.scheduler)
        submit_response = submit_use_case.execute(
            SubmitTaskRequest(
                code="print('Hello Developer')", timeout=300, cpu=2.0, memory=1024, user_id=user_id
            )
        )

        assert submit_response.success is True

        # 4. 验证任务已保存
        saved_task = self.task_repo.get_by_id("task_dev_001")
        assert saved_task is not None
        assert saved_task.user_id == user_id
        assert saved_task.cpu_request == 2.0
        assert saved_task.memory_request == 1024


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

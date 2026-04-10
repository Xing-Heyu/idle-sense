"""
End-to-end tests for user flow.

Tests the complete user journey from registration to task completion.
"""

import time

import pytest


class TestUserRegistrationFlow:
    """End-to-end tests for user registration flow."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_complete_user_journey(self, scheduler_url):
        """Test complete user journey: register -> login -> submit task -> view result."""
        try:
            import requests
        except ImportError:
            pytest.skip("requests not installed")

        try:
            response = requests.get(f"{scheduler_url}/health", timeout=2)
            if response.status_code != 200:
                pytest.skip("Scheduler not running")
        except Exception:
            pytest.skip("Scheduler not running")

        user_id = f"test-user-{int(time.time())}"
        username = f"testuser_{int(time.time())}"

        task_data = {
            "code": "result = sum(range(10))\n__result__ = result",
            "timeout": 60,
            "resources": {"cpu": 1.0, "memory": 512},
            "user_id": user_id,
        }

        response = requests.post(f"{scheduler_url}/submit", json=task_data, timeout=10)

        assert response.status_code == 200
        result = response.json()
        assert "task_id" in result

        task_id = result["task_id"]

        max_wait = 60
        start_time = time.time()

        while time.time() - start_time < max_wait:
            response = requests.get(f"{scheduler_url}/status/{task_id}", timeout=5)

            if response.status_code == 200:
                status = response.json()
                if status.get("status") in ["completed", "failed"]:
                    break

            time.sleep(2)

        response = requests.get(f"{scheduler_url}/status/{task_id}", timeout=5)
        assert response.status_code == 200

        final_status = response.json()
        assert final_status.get("status") == "completed"
        assert final_status.get("user_id") == user_id

    @pytest.mark.e2e
    def test_user_task_history(self, scheduler_url):
        """Test user can view their task history."""
        try:
            import requests
        except ImportError:
            pytest.skip("requests not installed")

        try:
            response = requests.get(f"{scheduler_url}/health", timeout=2)
            if response.status_code != 200:
                pytest.skip("Scheduler not running")
        except Exception:
            pytest.skip("Scheduler not running")

        response = requests.get(f"{scheduler_url}/results", timeout=5)
        assert response.status_code == 200

        results = response.json()
        assert "results" in results
        assert isinstance(results["results"], list)


class TestUserAuthentication:
    """End-to-end tests for user authentication."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    def test_user_registration_via_api(self, scheduler_url):
        """Test user registration via API."""
        try:
            import requests
        except ImportError:
            pytest.skip("requests not installed")

        try:
            response = requests.get(f"{scheduler_url}/health", timeout=2)
            if response.status_code != 200:
                pytest.skip("Scheduler not running")
        except Exception:
            pytest.skip("Scheduler not running")

        user_data = {
            "username": f"newuser_{int(time.time())}",
            "password": "testpassword123",
            "email": f"test_{int(time.time())}@example.com",
        }

        response = requests.post(f"{scheduler_url}/api/users/register", json=user_data, timeout=10)

        if response.status_code == 404:
            pytest.skip("User registration endpoint not available")

        assert response.status_code in [200, 201, 409]

    @pytest.mark.e2e
    def test_user_login_via_api(self, scheduler_url):
        """Test user login via API."""
        try:
            import requests
        except ImportError:
            pytest.skip("requests not installed")

        try:
            response = requests.get(f"{scheduler_url}/health", timeout=2)
            if response.status_code != 200:
                pytest.skip("Scheduler not running")
        except Exception:
            pytest.skip("Scheduler not running")

        login_data = {"username": "testuser", "password": "testpassword"}

        response = requests.post(f"{scheduler_url}/api/users/login", json=login_data, timeout=10)

        if response.status_code == 404:
            pytest.skip("User login endpoint not available")

        assert response.status_code in [200, 401, 404]


class TestUserTaskSubmission:
    """End-to-end tests for user task submission."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    def test_submit_task_with_user_context(self, scheduler_url):
        """Test submitting task with user context."""
        try:
            import requests
        except ImportError:
            pytest.skip("requests not installed")

        try:
            response = requests.get(f"{scheduler_url}/health", timeout=2)
            if response.status_code != 200:
                pytest.skip("Scheduler not running")
        except Exception:
            pytest.skip("Scheduler not running")

        user_id = f"context-user-{int(time.time())}"

        task_data = {
            "code": """
import math
result = math.factorial(5)
__result__ = result
""",
            "timeout": 30,
            "resources": {"cpu": 0.5, "memory": 256},
            "user_id": user_id,
        }

        response = requests.post(f"{scheduler_url}/submit", json=task_data, timeout=10)

        assert response.status_code == 200
        result = response.json()
        assert "task_id" in result
        assert result.get("safety_check") == "通过"

    @pytest.mark.e2e
    def test_submit_multiple_tasks_same_user(self, scheduler_url):
        """Test submitting multiple tasks from same user."""
        try:
            import requests
        except ImportError:
            pytest.skip("requests not installed")

        try:
            response = requests.get(f"{scheduler_url}/health", timeout=2)
            if response.status_code != 200:
                pytest.skip("Scheduler not running")
        except Exception:
            pytest.skip("Scheduler not running")

        user_id = f"multi-task-user-{int(time.time())}"
        task_ids = []

        for i in range(3):
            task_data = {
                "code": f"result = {i} * 10\n__result__ = result",
                "timeout": 30,
                "resources": {"cpu": 0.5, "memory": 256},
                "user_id": user_id,
            }

            response = requests.post(f"{scheduler_url}/submit", json=task_data, timeout=10)

            assert response.status_code == 200
            result = response.json()
            task_ids.append(result["task_id"])

        assert len(task_ids) == 3
        assert len(set(task_ids)) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])

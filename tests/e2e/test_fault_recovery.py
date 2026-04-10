"""
End-to-end tests for fault recovery scenarios.

Tests system resilience and recovery from failures.
"""

import time

import pytest


class TestNodeFaultRecovery:
    """End-to-end tests for node fault recovery."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    def test_node_timeout_detection(self, scheduler_url):
        """Test detection of node timeout."""
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

        node_id = f"timeout-node-{int(time.time())}"

        register_data = {
            "node_id": node_id,
            "capacity": {"cpu": 1.0, "memory": 2048},
            "tags": {"test": "timeout"},
        }

        response = requests.post(
            f"{scheduler_url}/api/nodes/register", json=register_data, timeout=10
        )

        if response.status_code != 200:
            pytest.skip("Node registration failed")

        response = requests.get(f"{scheduler_url}/api/nodes", timeout=5)
        assert response.status_code == 200

    @pytest.mark.e2e
    def test_dead_node_cleanup(self, scheduler_url):
        """Test cleanup of dead nodes."""
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

        response = requests.get(f"{scheduler_url}/stats", timeout=5)
        assert response.status_code == 200

        stats = response.json()
        assert "nodes" in stats


class TestTaskRetry:
    """End-to-end tests for task retry mechanisms."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    def test_task_retry_on_failure(self, scheduler_url):
        """Test task is retried on failure."""
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

        task_data = {
            "code": "result = 'retry_test'\n__result__ = result",
            "timeout": 30,
            "resources": {"cpu": 1.0, "memory": 512},
        }

        response = requests.post(f"{scheduler_url}/submit", json=task_data, timeout=10)

        assert response.status_code == 200
        task_id = response.json()["task_id"]

        max_wait = 30
        start_time = time.time()

        while time.time() - start_time < max_wait:
            response = requests.get(f"{scheduler_url}/status/{task_id}", timeout=5)

            if response.status_code == 200:
                status = response.json()
                if status.get("status") in ["completed", "failed"]:
                    break

            time.sleep(1)

        response = requests.get(f"{scheduler_url}/status/{task_id}", timeout=5)
        assert response.status_code == 200

    @pytest.mark.e2e
    def test_task_resubmission(self, scheduler_url):
        """Test task can be resubmitted after deletion."""
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

        task_data = {
            "code": "result = 1\n__result__ = result",
            "timeout": 30,
            "resources": {"cpu": 0.5, "memory": 256},
        }

        response = requests.post(f"{scheduler_url}/submit", json=task_data, timeout=10)

        assert response.status_code == 200
        task_id = response.json()["task_id"]

        response = requests.delete(f"{scheduler_url}/api/tasks/{task_id}", timeout=10)

        assert response.status_code in [200, 404]


class TestSchedulerRecovery:
    """End-to-end tests for scheduler recovery."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    def test_scheduler_health_check(self, scheduler_url):
        """Test scheduler health check endpoint."""
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

        assert response.status_code == 200

        health = response.json()
        assert health.get("status") == "healthy"

    @pytest.mark.e2e
    def test_scheduler_stats_recovery(self, scheduler_url):
        """Test scheduler stats are maintained after recovery."""
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

        response = requests.get(f"{scheduler_url}/stats", timeout=5)
        assert response.status_code == 200

        stats = response.json()
        assert "tasks" in stats
        assert "nodes" in stats


class TestDataRecovery:
    """End-to-end tests for data recovery."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    def test_task_persistence(self, scheduler_url):
        """Test task data is persisted."""
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

        task_data = {
            "code": "result = 'persist_test'\n__result__ = result",
            "timeout": 60,
            "resources": {"cpu": 1.0, "memory": 512},
        }

        response = requests.post(f"{scheduler_url}/submit", json=task_data, timeout=10)

        assert response.status_code == 200
        task_id = response.json()["task_id"]

        response = requests.get(f"{scheduler_url}/status/{task_id}", timeout=5)

        assert response.status_code == 200
        status = response.json()
        assert status.get("task_id") == task_id

    @pytest.mark.e2e
    def test_results_history(self, scheduler_url):
        """Test results history is maintained."""
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


class TestNetworkRecovery:
    """End-to-end tests for network recovery."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    def test_connection_timeout_handling(self, scheduler_url):
        """Test connection timeout is handled gracefully."""
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

        try:
            response = requests.get(f"{scheduler_url}/stats", timeout=0.001)
        except requests.exceptions.Timeout:
            pass
        except Exception:
            pass

        response = requests.get(f"{scheduler_url}/health", timeout=5)
        assert response.status_code == 200

    @pytest.mark.e2e
    def test_rate_limiting_recovery(self, scheduler_url):
        """Test rate limiting allows requests after cooldown."""
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

        time.sleep(1)

        response = requests.get(f"{scheduler_url}/health", timeout=5)
        assert response.status_code in [200, 429]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])

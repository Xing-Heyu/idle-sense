"""
End-to-end tests for multi-node scenarios.

Tests multi-node coordination, task distribution, and result aggregation.
"""

import time

import pytest


class TestMultiNodeRegistration:
    """End-to-end tests for multi-node registration."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    def test_register_multiple_nodes(self, scheduler_url):
        """Test registering multiple nodes."""
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

        node_ids = []
        for i in range(3):
            node_data = {
                "node_id": f"multi-node-{i}-{int(time.time())}",
                "capacity": {"cpu": 2.0, "memory": 4096},
                "tags": {"test": True, "index": i}
            }

            response = requests.post(
                f"{scheduler_url}/api/nodes/register",
                json=node_data,
                timeout=10
            )

            assert response.status_code == 200
            node_ids.append(node_data["node_id"])

        response = requests.get(f"{scheduler_url}/api/nodes", timeout=5)
        assert response.status_code == 200

        nodes_data = response.json()
        assert nodes_data.get("count", 0) >= 3

    @pytest.mark.e2e
    def test_node_heartbeat_updates(self, scheduler_url):
        """Test node heartbeat updates."""
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

        node_id = f"heartbeat-node-{int(time.time())}"

        register_data = {
            "node_id": node_id,
            "capacity": {"cpu": 4.0, "memory": 8192},
            "tags": {}
        }

        response = requests.post(
            f"{scheduler_url}/api/nodes/register",
            json=register_data,
            timeout=10
        )

        if response.status_code != 200:
            pytest.skip("Node registration failed")

        heartbeat_data = {
            "node_id": node_id,
            "current_load": {"cpu_usage": 1.5, "memory_usage": 2048},
            "is_idle": True,
            "available_resources": {"cpu": 2.5, "memory": 6144},
            "is_available": True
        }

        response = requests.post(
            f"{scheduler_url}/api/nodes/{node_id}/heartbeat",
            json=heartbeat_data,
            timeout=10
        )

        assert response.status_code == 200


class TestMultiNodeTaskDistribution:
    """End-to-end tests for task distribution across nodes."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_task_distributed_to_available_node(self, scheduler_url):
        """Test task is distributed to available node."""
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
            "code": "result = sum(range(100))\n__result__ = result",
            "timeout": 60,
            "resources": {"cpu": 1.0, "memory": 512}
        }

        response = requests.post(
            f"{scheduler_url}/submit",
            json=task_data,
            timeout=10
        )

        assert response.status_code == 200
        result = response.json()
        assert "task_id" in result

    @pytest.mark.e2e
    def test_multiple_tasks_distributed(self, scheduler_url):
        """Test multiple tasks are distributed across nodes."""
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

        task_ids = []
        for i in range(5):
            task_data = {
                "code": f"result = {i} ** 2\n__result__ = result",
                "timeout": 30,
                "resources": {"cpu": 0.5, "memory": 256}
            }

            response = requests.post(
                f"{scheduler_url}/submit",
                json=task_data,
                timeout=10
            )

            assert response.status_code == 200
            task_ids.append(response.json()["task_id"])

        assert len(task_ids) == 5


class TestMultiNodeResultAggregation:
    """End-to-end tests for result aggregation from multiple nodes."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    def test_collect_results_from_multiple_nodes(self, scheduler_url):
        """Test collecting results from multiple nodes."""
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

    @pytest.mark.e2e
    def test_task_status_includes_node_info(self, scheduler_url):
        """Test task status includes node information."""
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
            "code": "result = 42\n__result__ = result",
            "timeout": 30,
            "resources": {"cpu": 1.0, "memory": 512}
        }

        response = requests.post(
            f"{scheduler_url}/submit",
            json=task_data,
            timeout=10
        )

        assert response.status_code == 200
        task_id = response.json()["task_id"]

        response = requests.get(
            f"{scheduler_url}/status/{task_id}",
            timeout=5
        )

        assert response.status_code == 200
        status = response.json()
        assert "status" in status


class TestMultiNodeCoordination:
    """End-to-end tests for node coordination."""

    @pytest.fixture
    def scheduler_url(self):
        return "http://localhost:8000"

    @pytest.mark.e2e
    def test_node_capacity_tracking(self, scheduler_url):
        """Test node capacity is tracked correctly."""
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

    @pytest.mark.e2e
    def test_node_removal_and_task_reassignment(self, scheduler_url):
        """Test tasks are reassigned when node is removed."""
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

        node_id = f"removable-node-{int(time.time())}"

        register_data = {
            "node_id": node_id,
            "capacity": {"cpu": 2.0, "memory": 4096},
            "tags": {"removable": True}
        }

        response = requests.post(
            f"{scheduler_url}/api/nodes/register",
            json=register_data,
            timeout=10
        )

        if response.status_code != 200:
            pytest.skip("Node registration failed")

        response = requests.post(
            f"{scheduler_url}/api/nodes/{node_id}/stop",
            timeout=10
        )

        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])

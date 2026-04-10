"""
Pytest configuration and shared fixtures for idle-accelerator tests.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_psutil():
    """Mock psutil for cross-platform testing."""
    with (
        patch("psutil.cpu_percent") as cpu_mock,
        patch("psutil.virtual_memory") as mem_mock,
        patch("psutil.disk_usage") as disk_mock,
    ):

        cpu_mock.return_value = 25.0
        mem_mock.return_value = MagicMock(percent=50.0, available=4 * 1024 * 1024 * 1024)
        disk_mock.return_value = MagicMock(percent=40.0, free=50 * 1024 * 1024 * 1024)

        yield {"cpu": cpu_mock, "memory": mem_mock, "disk": disk_mock}


@pytest.fixture
def sample_task() -> dict:
    """Sample task for testing."""
    return {
        "code": "result = 1 + 1\n__result__ = result",
        "timeout": 300,
        "resources": {"cpu": 1.0, "memory": 512},
        "user_id": "test_user_001",
    }


@pytest.fixture
def sample_node_info() -> dict:
    """Sample node information for testing."""
    return {
        "node_id": "test_node_001",
        "capacity": {"cpu": 4.0, "memory": 8192, "disk": 50000},
        "tags": {"gpu": False, "location": "local"},
        "is_idle": True,
        "cpu_usage": 15.0,
        "memory_usage": 40.0,
    }


@pytest.fixture
def temp_storage_dir(tmp_path: Path) -> Path:
    """Create a temporary storage directory."""
    storage_dir = tmp_path / "test_storage"
    storage_dir.mkdir(exist_ok=True)
    return storage_dir


@pytest.fixture
def mock_scheduler_storage():
    """Mock scheduler storage for testing."""
    storage = MagicMock()
    storage.tasks = {}
    storage.nodes = {}
    storage.pending_tasks = []
    storage.results = {}
    return storage


@pytest.fixture
def mock_node_client():
    """Mock node client for testing."""
    client = MagicMock()
    client.node_id = "test_node_001"
    client.is_idle = True
    client.execute_task = AsyncMock(return_value={"result": "success", "output": "test output"})
    return client


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for API testing."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_requests_post():
    """Mock requests.post for API testing."""
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"task_id": 1, "status": "pending"}
        mock_post.return_value = mock_response
        yield mock_post


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks integration tests")
    config.addinivalue_line("markers", "e2e: marks end-to-end tests")
    config.addinivalue_line("markers", "windows: marks Windows-only tests")
    config.addinivalue_line("markers", "macos: marks macOS-only tests")


def pytest_collection_modifyitems(config, items):
    """Skip tests based on markers and platform."""
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    skip_windows = pytest.mark.skip(reason="Windows-only test")
    skip_macos = pytest.mark.skip(reason="macOS-only test")

    import platform

    current_platform = platform.system()

    for item in items:
        if "slow" in item.keywords and not config.getoption("--runslow", default=False):
            item.add_marker(skip_slow)
        if "windows" in item.keywords and current_platform != "Windows":
            item.add_marker(skip_windows)
        if "macos" in item.keywords and current_platform != "Darwin":
            item.add_marker(skip_macos)

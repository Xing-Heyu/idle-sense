import os

import pytest

REQUIRED_PATHS = [
    ("legacy/idle_sense/__init__.py", "file"),
    ("legacy/idle_sense/core.py", "file"),
    ("legacy/scheduler/simple_server.py", "file"),
    ("legacy/node/simple_client.py", "file"),
    ("requirements.txt", "file"),
    ("pyproject.toml", "file"),
    ("LICENSE", "file"),
    ("src/__init__.py", "file"),
    ("src/core/__init__.py", "file"),
    ("src/infrastructure/__init__.py", "file"),
    ("config/settings.py", "file"),
]


@pytest.mark.parametrize("path,path_type", REQUIRED_PATHS)
def test_required_path_exists(path, path_type):
    full_path = os.path.join(os.path.dirname(__file__), "..", path)
    if path_type == "file":
        assert os.path.isfile(full_path), f"Missing: {path}"
    else:
        assert os.path.isdir(full_path), f"Missing: {path}"

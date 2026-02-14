import os
import pytest

REQUIRED_PATHS = [
    ("idle_sense/__init__.py", "file"),
    ("idle_sense/core.py", "file"),
    ("scheduler/simple_server.py", "file"),
    ("node/simple_client.py", "file"),
    ("requirements.txt", "file"),
    ("pyproject.toml", "file"),
    ("LICENSE", "file"),
]

@pytest.mark.parametrize("path,path_type", REQUIRED_PATHS)
def test_required_path_exists(path, path_type):
    full_path = os.path.join(os.path.dirname(__file__), "..", path)
    if path_type == "file":
        assert os.path.isfile(full_path), f"Missing: {path}"
    else:
        assert os.path.isdir(full_path), f"Missing: {path}"

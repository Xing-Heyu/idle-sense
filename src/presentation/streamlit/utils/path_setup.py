"""
路径设置工具

确保项目根目录在 Python 路径中
"""

import sys
from pathlib import Path

_project_root = Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

PROJECT_ROOT = _project_root

__all__ = ["PROJECT_ROOT"]

"""
数据持久化基础设施工具模块

提供数据目录管理、数据库路径配置等持久化基础设施功能：
- 自动创建数据存储目录（数据库、备份等）
- 数据库路径配置管理，支持环境变量覆盖
- 统一的日志记录

使用示例：
    from src.infrastructure.persistence import ensure_data_dirs, get_db_path

    # 确保数据目录存在
    ensure_data_dirs()

    # 获取数据库文件路径
    db_path = get_db_path()
    print(f"数据库路径: {db_path}")

环境变量：
    IDLE_SENSE_DATA_DIR: 覆盖数据根目录（默认为项目根目录下的 data/）
    IDLE_SENSE_DB_PATH: 覆盖数据库文件完整路径（优先级最高）
"""

import os
from pathlib import Path
from typing import Optional

from src.infrastructure.utils.logger import get_logger

logger = get_logger("src.infrastructure.persistence")

# 项目根目录：从当前模块位置向上推导
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()

# 默认数据根目录名称
_DEFAULT_DATA_DIR_NAME = "data"

# 默认数据子目录
_DB_DIR_NAME = "db"
_BACKUP_DIR_NAME = "backups"

# 默认数据库文件名
_DEFAULT_DB_FILENAME = "idle_sense.db"

# 环境变量键名
_ENV_DATA_DIR = "IDLE_SENSE_DATA_DIR"
_ENV_DB_PATH = "IDLE_SENSE_DB_PATH"


def _get_data_root() -> Path:
    """
    获取数据根目录路径

    优先使用环境变量 IDLE_SENSE_DATA_DIR 指定的路径，
    否则使用项目根目录下的 data/ 目录。

    Returns:
        数据根目录的 Path 对象
    """
    env_data_dir = os.environ.get(_ENV_DATA_DIR)
    if env_data_dir:
        data_root = Path(env_data_dir).resolve()
        logger.info("使用环境变量指定的数据根目录", data_dir=str(data_root))
        return data_root

    data_root = _PROJECT_ROOT / _DEFAULT_DATA_DIR_NAME
    logger.debug("使用默认数据根目录", data_dir=str(data_root))
    return data_root


def get_db_path(db_filename: Optional[str] = None) -> Path:
    """
    获取数据库文件完整路径

    路径解析优先级：
    1. 环境变量 IDLE_SENSE_DB_PATH 指定的完整路径（最高优先级）
    2. 环境变量 IDLE_SENSE_DATA_DIR + db/ + db_filename
    3. 项目根目录/data/db/ + db_filename（默认）

    Args:
        db_filename: 数据库文件名，默认为 idle_sense.db

    Returns:
        数据库文件的完整 Path 对象

    Example:
        >>> db_path = get_db_path()
        >>> print(db_path)
        ... /path/to/project/data/db/idle_sense.db

        >>> custom_path = get_db_path("custom.db")
        >>> print(custom_path)
        ... /path/to/project/data/db/custom.db
    """
    filename = db_filename or _DEFAULT_DB_FILENAME

    # 最高优先级：直接通过环境变量指定完整数据库路径
    env_db_path = os.environ.get(_ENV_DB_PATH)
    if env_db_path:
        db_path = Path(env_db_path).resolve()
        logger.info(
            "使用环境变量指定的数据库路径",
            db_path=str(db_path),
            source="IDLE_SENSE_DB_PATH"
        )
        return db_path

    # 基于数据根目录构建路径
    data_root = _get_data_root()
    db_path = (data_root / _DB_DIR_NAME / filename).resolve()

    logger.debug("计算得到数据库路径", db_path=str(db_path))
    return db_path


def get_backup_dir() -> Path:
    """
    获取备份目录路径

    Returns:
        备份目录的 Path 对象
    """
    data_root = _get_data_root()
    backup_dir = (data_root / _BACKUP_DIR_NAME).resolve()
    return backup_dir


def get_db_dir() -> Path:
    """
    获取数据库文件所在目录路径

    Returns:
        数据库目录的 Path 对象
    """
    data_root = _get_data_root()
    db_dir = (data_root / _DB_DIR_NAME).resolve()
    return db_dir


def ensure_data_dirs() -> dict[str, Path]:
    """
    确保所有必要的持久化数据目录存在

    自动创建以下目录（如果不存在）：
    - data/db/: 数据库文件存储目录
    - data/backups/: 备份文件存储目录

    目录基于项目根目录或 IDLE_SENSE_DATA_DIR 环境变量创建。

    Returns:
        包含已创建/确认存在的目录路径字典，格式为：
        {
            "data_root": Path,   # 数据根目录
            "db_dir": Path,      # 数据库目录
            "backup_dir": Path   # 备份目录
        }

    Raises:
        OSError: 目录创建失败时抛出

    Example:
        >>> dirs = ensure_data_dirs()
        >>> for name, path in dirs.items():
        ...     print(f"{name}: {path}")
        data_root: /path/to/project/data
        db_dir: /path/to/project/data/db
        backup_dir: /path/to/project/data/backups
    """
    data_root = _get_data_root()
    db_dir = get_db_dir()
    backup_dir = get_backup_dir()

    created_dirs: dict[str, Path] = {}

    for dir_name, dir_path in [
        ("data_root", data_root),
        ("db_dir", db_dir),
        ("backup_dir", backup_dir),
    ]:
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            created_dirs[dir_name] = dir_path
            logger.info("数据目录就绪", directory=dir_name, path=str(dir_path))
        except PermissionError:
            logger.error(
                "权限不足，无法创建数据目录",
                directory=dir_name,
                path=str(dir_path)
            )
            raise
        except OSError as e:
            logger.error(
                "创建数据目录失败",
                directory=dir_name,
                path=str(dir_path),
                error=str(e)
            )
            raise

    logger.info("所有数据目录初始化完成", directories=list(created_dirs.keys()))
    return created_dirs


__all__ = [
    "ensure_data_dirs",
    "get_db_path",
    "get_backup_dir",
    "get_db_dir",
]

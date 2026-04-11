"""
用户仓储实现

基于文件的用户数据存储实现
"""

import json
import logging
import os
import secrets
from pathlib import Path
from typing import Optional

from src.core.entities import User
from src.core.interfaces.repositories import IUserRepository
from src.infrastructure.utils.cache_utils import MemoryCache


class FileUserRepository(IUserRepository):
    """基于文件的用户仓储实现 - 优化版（带缓存）"""

    def __init__(self, users_dir: Optional[str] = None):
        """
        初始化用户仓储

        Args:
            users_dir: 用户数据目录，默认使用项目根目录下的local_users
        """
        if users_dir is None:
            users_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "local_users"
            )
        self._users_dir = os.path.abspath(users_dir)
        Path(self._users_dir).mkdir(parents=True, exist_ok=True)

        self._user_cache = MemoryCache[str, User](max_size=1000, default_ttl=300)
        self._username_index: dict[str, str] = {}
        self._load_username_index()

    def _validate_user_id(self, user_id: str) -> bool:
        """
        验证用户ID是否安全

        Args:
            user_id: 用户ID

        Returns:
            bool: 是否安全
        """
        # 检查是否包含路径遍历字符
        dangerous_chars = ["..", "\\", "/", ":", "*", "?", '"', "<", ">", "|"]
        for char in dangerous_chars:
            if char in user_id:
                return False

        # 限制ID长度
        return not len(user_id) > 100

    def _get_safe_user_file(self, user_id: str) -> str:
        """
        获取安全的用户文件路径

        防止路径遍历攻击：
        1. 验证用户ID
        2. 规范化路径
        3. 确保路径在允许的目录内

        Args:
            user_id: 用户ID

        Returns:
            str: 安全的文件路径

        Raises:
            ValueError: 如果路径不安全
        """
        # 首先验证用户ID
        if not self._validate_user_id(user_id):
            raise ValueError(f"Invalid user_id: {user_id}")

        # 构造基础路径
        base_path = os.path.join(self._users_dir, f"{user_id}.json")

        # 规范化路径
        normalized_path = os.path.normpath(base_path)

        # 获取绝对路径
        absolute_path = os.path.abspath(normalized_path)

        # 确保路径在允许的目录内
        if not absolute_path.startswith(self._users_dir):
            raise ValueError(f"Path traversal attempt detected: {user_id}")

        # 双重检查：使用pathlib确保安全
        safe_path = Path(absolute_path)
        expected_parent = Path(self._users_dir)

        if not safe_path.is_relative_to(expected_parent):
            raise ValueError(f"Path traversal attempt detected: {user_id}")

        return absolute_path

    def _get_user_file(self, user_id: str) -> str:
        """获取用户文件路径（带安全验证）"""
        return self._get_safe_user_file(user_id)

    def _load_username_index(self):
        """加载用户名索引（优化 get_by_username）"""
        if os.path.exists(self._users_dir):
            for file_name in os.listdir(self._users_dir):
                if file_name.endswith(".json"):
                    user_id = file_name[:-5]
                    user_file = self._get_user_file(user_id)
                    try:
                        with open(user_file, encoding="utf-8") as f:
                            data = json.load(f)
                            if "username" in data:
                                self._username_index[data["username"]] = user_id
                    except (OSError, json.JSONDecodeError) as e:
                        logging.warning(f"[UserRepository] 加载用户索引失败 {user_id}: {e}")
                    except Exception as e:
                        logging.error(f"[UserRepository] 加载用户索引异常 {user_id}: {e}")

    def _update_index(self, user: User):
        """更新用户名索引"""
        self._username_index[user.username] = user.user_id

    def _remove_from_index(self, user_id: str):
        """从索引中移除用户"""
        to_remove = []
        for username, uid in self._username_index.items():
            if uid == user_id:
                to_remove.append(username)
        for username in to_remove:
            del self._username_index[username]

    def get_by_id(self, user_id: str) -> Optional[User]:
        """根据ID获取用户（带缓存）"""
        cached_user = self._user_cache.get(user_id)
        if cached_user is not None:
            return cached_user

        user_file = self._get_user_file(user_id)
        if os.path.exists(user_file):
            with open(user_file, encoding="utf-8") as f:
                data = json.load(f)
                user = User.from_dict(data)
                self._user_cache.set(user_id, user)
                return user
        return None

    def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户（使用索引优化）"""
        if username in self._username_index:
            user_id = self._username_index[username]
            return self.get_by_id(user_id)
        return None

    def save(self, user: User) -> User:
        """保存用户（更新缓存和索引）"""
        user_file = self._get_user_file(user.user_id)
        with open(user_file, "w", encoding="utf-8") as f:
            json.dump(user.to_dict(), f, ensure_ascii=False, indent=2)

        self._user_cache.set(user.user_id, user)
        self._update_index(user)
        return user

    def update(self, user: User) -> User:
        """更新用户"""
        return self.save(user)

    def delete(self, user_id: str) -> bool:
        """删除用户（清理缓存和索引）"""
        user_file = self._get_user_file(user_id)
        if os.path.exists(user_file):
            os.remove(user_file)
            self._user_cache.delete(user_id)
            self._remove_from_index(user_id)
            return True
        return False

    def list_all(self) -> list[User]:
        """获取所有用户（优化版）"""
        users = []
        if os.path.exists(self._users_dir):
            for file_name in os.listdir(self._users_dir):
                if file_name.endswith(".json"):
                    user_id = file_name[:-5]
                    user = self.get_by_id(user_id)
                    if user:
                        users.append(user)
        return users

    def exists(self, username: str) -> bool:
        """检查用户名是否存在（使用索引优化）"""
        return username in self._username_index

    def find_available_username(self, username: str) -> str:
        """查找可用的用户名"""
        users = self.list_all()
        existing_usernames = [user.username for user in users]

        if username not in existing_usernames:
            return username

        counter = 1
        while True:
            new_username = f"{username}_{counter}"
            if new_username not in existing_usernames:
                return new_username
            counter += 1
            if counter > 999:
                return f"{username}_{secrets.randbelow(9000) + 1000}"


__all__ = ["FileUserRepository"]

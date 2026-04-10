#!/usr/bin/env python3
import os
import sys
import hashlib
import threading
import queue
import time
import subprocess
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum


class FileType(Enum):
    PYTHON = "Python"
    JAVASCRIPT = "JavaScript"
    HTML = "HTML"
    CSS = "CSS"
    MARKDOWN = "Markdown"
    YAML = "YAML"
    JSON = "JSON"
    IMAGE = "Image"
    DOCUMENT = "Document"
    CONFIG = "Config"
    OTHER = "Other"


class UpdatePriority(Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass
class FileInfo:
    path: str
    file_type: FileType
    size: int
    modified_time: float
    git_commit: Optional[str] = None
    git_commit_time: Optional[float] = None
    git_author: Optional[str] = None
    content_hash: Optional[str] = None
    needs_update: bool = False
    update_priority: UpdatePriority = UpdatePriority.LOW
    update_suggestion: str = ""


class FileScanner:
    def __init__(self, root_dir: str, num_workers: int = 8):
        self.root_dir = Path(root_dir).resolve()
        self.num_workers = num_workers
        self.file_queue = queue.Queue()
        self.results: List[FileInfo] = []
        self.lock = threading.Lock()
        self.git_available = self._check_git_available()
        self.exclude_dirs = {".git", "__pycache__", ".venv", "node_modules", ".mypy_cache", ".tox"}
        self.exclude_files = {".DS_Store", "Thumbs.db"}
        
    def _check_git_available(self) -> bool:
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
            return (self.root_dir / ".git").exists()
        except Exception:
            return False
    
    def _get_file_type(self, file_path: Path) -> FileType:
        suffix = file_path.suffix.lower()
        type_map = {
            ".py": FileType.PYTHON,
            ".js": FileType.JAVASCRIPT,
            ".ts": FileType.JAVASCRIPT,
            ".jsx": FileType.JAVASCRIPT,
            ".tsx": FileType.JAVASCRIPT,
            ".html": FileType.HTML,
            ".htm": FileType.HTML,
            ".css": FileType.CSS,
            ".scss": FileType.CSS,
            ".sass": FileType.CSS,
            ".md": FileType.MARKDOWN,
            ".markdown": FileType.MARKDOWN,
            ".yaml": FileType.YAML,
            ".yml": FileType.YAML,
            ".json": FileType.JSON,
            ".png": FileType.IMAGE,
            ".jpg": FileType.IMAGE,
            ".jpeg": FileType.IMAGE,
            ".gif": FileType.IMAGE,
            ".svg": FileType.IMAGE,
            ".pdf": FileType.DOCUMENT,
            ".doc": FileType.DOCUMENT,
            ".docx": FileType.DOCUMENT,
            ".txt": FileType.DOCUMENT,
            ".ini": FileType.CONFIG,
            ".cfg": FileType.CONFIG,
            ".conf": FileType.CONFIG,
            ".env": FileType.CONFIG,
            ".toml": FileType.CONFIG,
        }
        return type_map.get(suffix, FileType.OTHER)
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        hash_obj = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception:
            return ""
    
    def _get_git_info(self, file_path: Path) -> Dict:
        if not self.git_available:
            return {}
        
        try:
            rel_path = file_path.relative_to(self.root_dir)
            result = subprocess.run(
                ["git", "log", "-1", "--format=%H|%ct|%an", str(rel_path)],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                check=True
            )
            if result.stdout.strip():
                parts = result.stdout.strip().split("|", 2)
                if len(parts) == 3:
                    return {
                        "commit": parts[0],
                        "commit_time": float(parts[1]),
                        "author": parts[2]
                    }
        except Exception:
            pass
        return {}
    
    def _analyze_file(self, file_path: Path) -> FileInfo:
        stat = file_path.stat()
        file_type = self._get_file_type(file_path)
        
        file_info = FileInfo(
            path=str(file_path.relative_to(self.root_dir)),
            file_type=file_type,
            size=stat.st_size,
            modified_time=stat.st_mtime
        )
        
        file_info.content_hash = self._calculate_file_hash(file_path)
        
        git_info = self._get_git_info(file_path)
        if git_info:
            file_info.git_commit = git_info.get("commit")
            file_info.git_commit_time = git_info.get("commit_time")
            file_info.git_author = git_info.get("author")
        
        self._determine_update_need(file_info, stat.st_mtime)
        
        return file_info
    
    def _determine_update_need(self, file_info: FileInfo, mtime: float):
        now = time.time()
        days_since_modified = (now - mtime) / (24 * 3600)
        
        suggestions = []
        
        if file_info.file_type in [FileType.PYTHON, FileType.JAVASCRIPT]:
            if days_since_modified > 180:
                file_info.needs_update = True
                file_info.update_priority = UpdatePriority.HIGH
                suggestions.append(f"文件超过6个月未修改 ({int(days_since_modified)}天)，建议检查是否需要更新")
            elif days_since_modified > 90:
                file_info.needs_update = True
                file_info.update_priority = UpdatePriority.MEDIUM
                suggestions.append(f"文件超过3个月未修改 ({int(days_since_modified)}天)，建议关注")
        
        if file_info.file_type == FileType.CONFIG:
            if days_since_modified > 365:
                file_info.needs_update = True
                file_info.update_priority = UpdatePriority.CRITICAL
                suggestions.append("配置文件超过1年未更新，建议审查")
        
        if file_info.git_commit_time:
            days_since_commit = (now - file_info.git_commit_time) / (24 * 3600)
            if days_since
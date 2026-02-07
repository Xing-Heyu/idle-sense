"""
config/config_manager.py
配置管理器 - 实现配置继承和类型转换
"""

import os
import yaml
from typing import Any, Dict, Optional, Union
from pathlib import Path
from .default_settings import DEFAULTS

class ConfigManager:
    """配置管理器，负责加载和合并配置"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self._config_cache: Dict[str, Any] = {}
        
        # 配置搜索路径
        self.search_paths = [
            config_file,
            "config.yaml",
            "config/config.yaml",
            Path.home() / ".idle-accelerator" / "config.yaml",
            "/etc/idle-accelerator/config.yaml"
        ]
    
    def load_config(self) -> Dict[str, Any]:
        """加载并合并所有配置源"""
        # 1. 加载默认配置
        config = self._load_defaults()
        
        # 2. 加载YAML配置文件
        yaml_config = self._load_yaml_config()
        config = self._deep_merge(config, yaml_config)
        
        # 3. 加载环境变量
        env_config = self._load_env_vars()
        config = self._deep_merge(config, env_config)
        
        self._config_cache = config
        return config
    
    def _load_defaults(self) -> Dict[str, Any]:
        """加载Python默认配置"""
        # 将DEFAULTS对象转换为嵌套字典
        defaults_dict = {}
        for key, value in DEFAULTS.items():
            if hasattr(value, '__dict__'):
                # 如果是类实例，转换其属性
                defaults_dict[key] = {
                    k: v for k, v in value.__dict__.items() 
                    if not k.startswith('_')
                }
            else:
                defaults_dict[key] = value
        return defaults_dict
    
    def _load_yaml_config(self) -> Dict[str, Any]:
        """加载YAML配置文件"""
        config_file = self._find_config_file()
        if not config_file or not os.path.exists(config_file):
            return {}
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Failed to load config file {config_file}: {e}")
            return {}
    
    def _find_config_file(self) -> Optional[str]:
        """查找配置文件"""
        for path in self.search_paths:
            if path and os.path.exists(path):
                return str(path)
        return None
    
    def _load_env_vars(self) -> Dict[str, Any]:
        """从环境变量加载配置"""
        env_config = {}
        
        # 环境变量前缀映射
        env_prefixes = {
            'SCHEDULER_': ['scheduler'],
            'NODE_': ['node'],
            'WEB_': ['web'],
            'MONITORING_': ['monitoring'],
            'REDIS_': ['scheduler', 'redis']
        }
        
        for env_key, env_value in os.environ.items():
            # 处理每个前缀
            for prefix, config_path in env_prefixes.items():
                if env_key.startswith(prefix):
                    # 转换环境变量名：SCHEDULER_PORT -> scheduler.port
                    config_key = env_key[len(prefix):].lower()
                    
                    # 转换值类型
                    converted_value = self._convert_env_value(env_value)
                    
                    # 构建嵌套字典路径
                    current = env_config
                    for path_part in config_path[:-1]:
                        if path_part not in current:
                            current[path_part] = {}
                        current = current[path_part]
                    
                    # 设置最终值
if config_path[-1] not in current:
    current[config_path[-1]] = {}
current[config_path[-1]][config_key] = converted_value
        
        return env_config
    
    def _convert_env_value(self, value: str) -> Any:
        """转换环境变量值为适当类型"""
        # 布尔值
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False
        
        # 整数
        if value.isdigit():
            return int(value)
        
        # 浮点数
        try:
            return float(value)
        except ValueError:
            pass
        
        # 列表（逗号分隔）
        if ',' in value:
            return [self._convert_env_value(v.strip()) for v in value.split(',')]
        
        # 默认返回字符串
        return value
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """深度合并两个字典"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # 递归合并嵌套字典
                result[key] = self._deep_merge(result[key], value)
            else:
                # 覆盖或添加新键
                result[key] = value
        
        return result
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """获取配置值，支持点分隔路径"""
        if not self._config_cache:
            self.load_config()
        
        # 分割路径：scheduler.port -> ['scheduler', 'port']
        parts = key_path.split('.')
        
        current = self._config_cache
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        
        return current

# 全局配置管理器实例
_config_manager = ConfigManager()

def get_config(key_path: str = "", default: Any = None) -> Any:
    """获取配置的便捷函数"""
    if key_path:
        return _config_manager.get(key_path, default)
    return _config_manager.load_config()

def reload_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """重新加载配置"""
    global _config_manager
    _config_manager = ConfigManager(config_file)
    return _config_manager.load_config()
  # 在任何文件中使用配置

# 方法1: 直接获取配置值
from config.config_manager import get_config

# 获取调度中心端口
port = get_config("scheduler.port")  # 返回: 8000

# 获取节点检查间隔
check_interval = get_config("node.idle_detection.check_interval")  # 返回: 30

# 方法2: 获取整个配置
config = get_config()  # 返回完整配置字典

# 方法3: 代码中使用
import os
from config.default_settings import SCHEDULER

# 优先使用环境变量，否则用默认值
port = int(os.getenv("SCHEDULER_PORT", SCHEDULER.PORT))

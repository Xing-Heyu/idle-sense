"""
local_authorization.py
本地操作授权管理器 - 实现合规授权方案
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class LocalOperationAuthorization:
    """本地操作授权管理器"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
    def request_folder_creation_authorization(self, user_id: str, username: str, 
                                            target_paths: Dict[str, str]) -> Dict[str, Any]:
        """
        请求文件夹创建授权
        
        Args:
            user_id: 用户ID
            username: 用户名
            target_paths: 目标路径字典
        
        Returns:
            授权结果
        """
        # 构建授权提示内容
        authorization_prompt = self._build_authorization_prompt(target_paths)
        
        # 记录授权请求
        request_log = {
            "user_id": user_id,
            "username": username,
            "operation_type": "文件夹创建授权",
            "target_paths": target_paths,
            "request_time": datetime.now().isoformat(),
            "status": "pending"
        }
        self._log_operation(request_log)
        
        # 返回授权提示信息（前端需要实现弹窗）
        return {
            "requires_authorization": True,
            "authorization_prompt": authorization_prompt,
            "operation_details": {
                "type": "文件夹创建",
                "paths": target_paths,
                "user_id": user_id
            }
        }
    
    def confirm_authorization(self, user_id: str, operation_details: Dict[str, Any], 
                            user_agreed: bool) -> Dict[str, Any]:
        """
        确认授权结果
        
        Args:
            user_id: 用户ID
            operation_details: 操作详情
            user_agreed: 用户是否同意
        
        Returns:
            授权确认结果
        """
        # 记录授权确认
        confirmation_log = {
            "user_id": user_id,
            "operation_type": operation_details.get("type", "unknown"),
            "target_paths": operation_details.get("paths", {}),
            "confirmation_time": datetime.now().isoformat(),
            "user_agreed": user_agreed,
            "status": "confirmed" if user_agreed else "rejected"
        }
        
        self._log_operation(confirmation_log)
        
        if not user_agreed:
            return {
                "authorized": False,
                "message": "用户拒绝授权，操作已终止",
                "log_entry": confirmation_log
            }
        
        return {
            "authorized": True,
            "message": "用户已确认授权，可以执行本地操作",
            "log_entry": confirmation_log
        }
    
    def _build_authorization_prompt(self, target_paths: Dict[str, str]) -> Dict[str, str]:
        """构建授权提示内容"""
        
        # 构建路径描述
        path_descriptions = []
        for path_type, path in target_paths.items():
            if path_type == "user_data":
                path_descriptions.append(f"用户数据文件夹: {path}")
            elif path_type == "temp_data":
                path_descriptions.append(f"临时数据文件夹: {path}")
            else:
                path_descriptions.append(f"{path_type}: {path}")
        
        paths_text = "\n".join(path_descriptions)
        
        return {
            "title": "【本地操作授权】",
            "content": f"""
你即将触发「文件夹创建功能」，该操作将在你的设备本地执行文件夹创建操作：

{paths_text}

所有操作均由你主动授权发起，操作结果由你自行负责。

确认授权后，系统将仅执行该单次操作，无你的再次确认，不会进行任何额外本地读写操作。

□ 我已阅读并确认授权本次本地操作
""",
            "disclaimer": """
【本地文件操作免责声明】
1. 本软件所有本地文件夹/文件操作，均需用户主动点击授权后执行，无用户授权，系统不会发起任何本地读写、创建、修改、删除操作。
2. 用户授权后，系统仅执行用户明确触发的单次操作，不会在后台进行任何未告知的本地文件操作，不会收集、上传本地文件中的任何数据。
3. 因用户授权操作导致的本地文件目录变更、数据覆盖、设备存储异常等问题，均由用户自行承担责任；本软件开发方仅提供功能实现，不对操作结果及后续风险负责。
4. 如用户发现软件存在未授权本地操作行为，可立即停止使用并反馈，开发方将第一时间核查处理。
"""
        }
    
    def _log_operation(self, log_entry: Dict[str, Any]):
        """记录操作日志"""
        try:
            log_file = self.log_dir / "local_operations.log"
            
            # 如果文件不存在，创建并写入header
            if not log_file.exists():
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.write("# 本地操作授权日志\n")
                    f.write("# 格式: JSONL (每行一个JSON对象)\n")
                    f.write("# 记录所有本地文件操作授权请求和确认\n\n")
            
            # 追加日志条目
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                
        except Exception as e:
            print(f"警告: 无法写入操作日志: {e}")
    
    def get_operation_logs(self, user_id: Optional[str] = None, 
                          start_time: Optional[str] = None,
                          end_time: Optional[str] = None) -> list:
        """获取操作日志"""
        try:
            log_file = self.log_dir / "local_operations.log"
            if not log_file.exists():
                return []
            
            logs = []
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    try:
                        log_entry = json.loads(line)
                        
                        # 过滤条件
                        if user_id and log_entry.get('user_id') != user_id:
                            continue
                        
                        if start_time and log_entry.get('request_time', '') < start_time:
                            continue
                        
                        if end_time and log_entry.get('request_time', '') > end_time:
                            continue
                        
                        logs.append(log_entry)
                        
                    except json.JSONDecodeError:
                        continue
            
            return logs
            
        except Exception as e:
            print(f"警告: 无法读取操作日志: {e}")
            return []


# 全局授权管理器实例
authorization_manager = LocalOperationAuthorization()
# c:\idle-sense\user_management\api.py
from fastapi import APIRouter, HTTPException,
 Header
from typing import Dict,
 Any
from .auth import
 AuthManager
from .quota import
 QuotaManager

router = APIRouter()
auth_manager = AuthManager()
quota_manager = QuotaManager()

@router.post("/register")
async def register_user(username: str, email: str):
    """用户注册接口"""
    result = auth_manager.register_user(username, email)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    # 初始化配额
    user_id = result["user_id"]
    quota_manager.quotas[user_id] = result["quota"]
    
    # 创建会话
    session_id = auth_manager.create_session(user_id)
    
    return {
        "success": True,
        "session_id": session_id,
        "user": result["user"],
        "quota": result["quota"]
    }

@router.get("/quota")
async def get_quota(x_session_id: str = Header(...)):
    """获取用户配额"""
    user_id = auth_manager.validate_session(x_session_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="未授权")
    
    quota_result = quota_manager.check_quota(user_id)
    if not quota_result["allowed"]:
        raise HTTPException(status_code=403, detail=quota_result["error"])
    
    return
 quota_result

@router.post("/quota/consume")
async def consume_quota(x_session_id: str = Header(...)):
    """消耗配额"""
    user_id = auth_manager.validate_session(x_session_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="未授权")
    
    if not quota_manager.consume_quota(user_id):
        raise HTTPException(status_code=403, detail="配额不足")
    
    return {"success": True, "message": "配额消耗成功"}

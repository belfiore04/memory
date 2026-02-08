from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any, Optional
from services.auth_service import AuthService
from services.chat_log_service import ChatLogService
from routers.auth import get_current_admin
from pydantic import BaseModel

class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None

router = APIRouter(prefix="/admin", tags=["Admin"])

_auth_service = AuthService()
_chat_log_service = ChatLogService()

@router.get("/users", dependencies=[Depends(get_current_admin)])
async def get_all_users():
    """获取所有用户列表 (Admin Only)"""
    return _auth_service.get_all_users()

@router.put("/users/{user_id}", dependencies=[Depends(get_current_admin)])
async def update_user(user_id: str, update: UserUpdate):
    """更新用户信息 (角色/状态) (Admin Only)"""
    success = True
    if update.role is not None:
        if not _auth_service.update_user_role(user_id, update.role):
            success = False
            
    if update.is_active is not None:
        if not _auth_service.update_user_status(user_id, update.is_active):
            success = False
            
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update user")
        
    return {"message": "User updated successfully"}

@router.get("/users/{user_id}/history", dependencies=[Depends(get_current_admin)])
async def get_user_chat_history(user_id: str, limit: int = 20, before_id: int = None):
    """获取指定用户的聊天历史 (Admin Only, Paginated)"""
    history = _chat_log_service.get_history(user_id, limit=limit, before_id=before_id)
    return {
        "user_id": user_id,
        "history": history,
        "next_before_id": history[-1]["id"] if history else None
    }

@router.get("/stats", dependencies=[Depends(get_current_admin)])
async def get_system_stats(since: Optional[str] = None):
    """
    获取系统统计信息
    - since: 可选，ISO 格式时间字符串 (YYYY-MM-DD HH:MM:SS)，用于获取该时间之后的新增数据
    """
    users = _auth_service.get_all_users()
    chat_stats = _chat_log_service.get_stats()
    
    response = {
        "total_users": len(users),
        "active_users": len([u for u in users if u.get("is_active", 1)]),
        "today_active_users": chat_stats["today_active_users"],
        "today_chat_rounds": chat_stats["today_chat_rounds"]
    }
    
    if since:
        since_users = _auth_service.get_users_count_since(since)
        since_chat_stats = _chat_log_service.get_stats_since(since)
        
        response["since_new_users"] = since_users
        response["since_active_users"] = since_chat_stats["active_users"]
        response["since_chat_rounds"] = since_chat_stats["chat_rounds"]
        
    return response

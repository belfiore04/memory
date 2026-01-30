#!/usr/bin/env python3
"""
Focus Router - 管理用户的近期关注和耳语者建议
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from services.focus_service import FocusService
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/focus", tags=["Focus & Whisper"])

# ==================== 单例服务 ====================
_focus_service: Optional[FocusService] = None
def get_focus_service() -> FocusService:
    global _focus_service
    if _focus_service is None:
        _focus_service = FocusService()
    return _focus_service


# ==================== 响应模型 ====================
class FocusItem(BaseModel):
    content: str

class FocusListResponse(BaseModel):
    user_id: str
    focus_list: List[str]
    count: int

class WhisperResponse(BaseModel):
    user_id: str
    suggestion: Optional[str]
    created_at: Optional[str]
    is_consumed: Optional[bool]


# ==================== API ====================

@router.get("/{user_id}", response_model=FocusListResponse)
async def get_user_focus(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    focus_service: FocusService = Depends(get_focus_service)
):
    """
    获取用户当前所有活跃的关注点
    
    **输入示例**: `GET /focus/user_abc123`
    
    **输出示例**:
    ```json
    {
        "user_id": "user_abc123",
        "focus_list": ["正在找工作", "减肥中", "学习弹吉他"],
        "count": 3
    }
    ```
    """
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    
    try:
        focus_list = focus_service.get_active_focus(user_id)
        return {
            "user_id": user_id,
            "focus_list": focus_list,
            "count": len(focus_list)
        }
    except Exception as e:
        logger.error(f"获取关注点失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/whisper", response_model=WhisperResponse)
async def get_latest_whisper(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    focus_service: FocusService = Depends(get_focus_service)
):
    """
    获取最新一条耳语者建议（仅查看，不消费）
    
    **输入示例**: `GET /focus/user_abc123/whisper`
    
    **输出示例**:
    ```json
    {
        "user_id": "user_abc123",
        "suggestion": "用户感到受挫，下一轮请主动询问他具体是哪个方向的岗位，并给予具体的行业鼓励。",
        "created_at": "2026-01-28 15:10:00",
        "is_consumed": false
    }
    ```
    
    **字段说明**:
    - `suggestion`: 耳语者生成的策略建议
    - `is_consumed`: 是否已被主对话消费（注入到 Prompt 中）
    """
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    
    try:
        whisper = focus_service.peek_latest_whisper(user_id)
        if whisper:
            return {
                "user_id": user_id,
                "suggestion": whisper["suggestion"],
                "created_at": str(whisper["created_at"]),
                "is_consumed": whisper["is_consumed"]
            }
        else:
            return {
                "user_id": user_id,
                "suggestion": None,
                "created_at": None,
                "is_consumed": None
            }
    except Exception as e:
        logger.error(f"获取耳语建议失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{user_id}")
async def clear_user_focus(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    focus_service: FocusService = Depends(get_focus_service)
):
    """
    清空用户所有活跃的关注点
    
    **输入示例**: `DELETE /focus/user_abc123`
    
    **输出示例**:
    ```json
    {
        "success": true,
        "message": "已清空所有关注点"
    }
    ```
    """
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    
    try:
        success = focus_service.clear_all_focus(user_id)
        if success:
            return {"success": True, "message": "已清空所有关注点"}
        else:
            raise HTTPException(status_code=500, detail="清空失败")
    except Exception as e:
        logger.error(f"清空关注点失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

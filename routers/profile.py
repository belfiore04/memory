from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
from services.profile_service import ProfileService
from schemas.common import MessageItem
from fastapi import Depends
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["Profile"])

# 初始化画像服务（延迟初始化）
_profile_service: Optional[ProfileService] = None

def get_profile_service() -> ProfileService:
    """获取画像服务实例（单例模式）"""
    global _profile_service
    if _profile_service is None:
        logger.info("初始化画像服务...")
        _profile_service = ProfileService()
        logger.info("画像服务初始化完成")
    return _profile_service

# ==================== 请求/响应模型 ====================

class ExtractProfileRequest(BaseModel):
    """画像抽取请求 (不再需要 user_id)"""
    messages: List[MessageItem] = Field(..., description="对话消息列表")

class UpdateSlotRequest(BaseModel):
    """槽位更新请求"""
    key: str = Field(..., description="槽位 key")
    value: str = Field(..., description="槽位值")

# ==================== Profile API ====================

@router.get("/{user_id}")
async def get_profile(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """获取用户完整画像"""
    try:
        service = get_profile_service()
        slots = service.get_all_slots(user_id)
        return {"user_id": user_id, "slots": slots}
    except Exception as e:
        logger.error(f"获取画像失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{user_id}/extract")
async def extract_profile(user_id: str, request: ExtractProfileRequest, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """从对话中抽取槽位信息并更新画像"""
    try:
        service = get_profile_service()
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        result = service.extract_slots(user_id, messages)
        return result
    except Exception as e:
        logger.error(f"抽取画像失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{user_id}/slot")
async def update_slot(user_id: str, request: UpdateSlotRequest, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """手动更新单个槽位"""
    try:
        service = get_profile_service()
        result = service.update_slot(user_id, request.key, request.value)
        return result
    except Exception as e:
        logger.error(f"更新槽位失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{user_id}")
async def clear_profile(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """清空用户画像"""
    try:
        service = get_profile_service()
        result = service.clear_profile(user_id)
        return result
    except Exception as e:
        logger.error(f"清空画像失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

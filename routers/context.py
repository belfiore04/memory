from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
from services.context_service import ContextService
from schemas.common import MessageItem
from fastapi import Depends
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/context", tags=["Context"])

# 初始化上下文服务（延迟初始化）
_context_service: Optional[ContextService] = None

def get_context_service() -> ContextService:
    """获取上下文服务实例（单例模式）"""
    global _context_service
    if _context_service is None:
        logger.info("初始化上下文服务...")
        _context_service = ContextService()
        logger.info("上下文服务初始化完成")
    return _context_service

# ==================== 请求/响应模型 ====================

class ContextAppendRequest(BaseModel):
    """上下文追加请求 (不再需要 user_id)"""
    messages: List[MessageItem] = Field(..., description="要追加的消息列表")

class ContextGetResponse(BaseModel):
    """上下文获取响应"""
    summary: str = Field(..., description="当前摘要")
    history: List[dict] = Field(..., description="最近未摘要的对话历史")
    full_text: str = Field(..., description="拼接好的完整上下文文本")

# ==================== Context API ====================

@router.get("/{user_id}", response_model=ContextGetResponse)
async def get_context(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """
    获取上下文（可能会触发自动概括）
    """
    try:
        service = get_context_service()
        result = service.get_context(user_id)
        return ContextGetResponse(**result)
    except Exception as e:
        logger.error(f"上下文获取失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{user_id}/append", response_model=dict)
async def append_context(user_id: str, request: ContextAppendRequest, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """
    追加对话记录到上下文
    """
    try:
        service = get_context_service()
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        service.append_message(user_id, messages)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"上下文追加失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{user_id}", response_model=dict)
async def clear_context(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """
    清空指定用户的上下文
    """
    try:
        service = get_context_service()
        service.clear_context(user_id)
        return {"status": "success", "message": f"Context cleared for user {user_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{user_id}/summary", response_model=dict)
async def clear_summary_only(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """
    仅清空指定用户的摘要，保留最近对话历史
    """
    try:
        service = get_context_service()
        service.clear_summary(user_id)
        return {"status": "success", "message": f"Context summary cleared for user {user_id}"}
    except Exception as e:
        logger.error(f"上下文摘要清空失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

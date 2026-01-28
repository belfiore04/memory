from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
from services.memory_service import MemoryService
from schemas.common import MessageItem
from fastapi import Depends
from routers.auth import get_current_user

# 配置日志
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["Memory"])

# 初始化记忆服务（延迟初始化）
_memory_service: Optional[MemoryService] = None

def get_memory_service() -> MemoryService:
    """获取记忆服务实例（单例模式）"""
    global _memory_service
    if _memory_service is None:
        logger.info("初始化记忆服务...")
        _memory_service = MemoryService()
        logger.info("记忆服务初始化完成")
    return _memory_service

# ==================== 请求/响应模型 ====================

class RetrieveRequest(BaseModel):
    """检索请求模型 (不再需要 user_id)"""
    query: str = Field(..., description="用户查询内容")

class RetrieveResponse(BaseModel):
    """检索响应模型"""
    should_retrieve: bool = Field(..., description="是否需要检索")
    reason: str = Field(..., description="判断原因")
    memories: List[dict] = Field(default_factory=list, description="相关记忆列表（Edge 级别细节）")
    episodes: List[dict] = Field(default_factory=list, description="完整记忆列表（Episodic 原始故事）")

class SmartStoreRequest(BaseModel):
    """智能存储请求模型 (不再需要 user_id)"""
    messages: List[MessageItem] = Field(..., description="对话消息列表")

class SmartStoreResponse(BaseModel):
    """智能存储响应模型"""
    should_store: bool = Field(..., description="是否需要存储")
    reason: str = Field(..., description="判断原因")
    success: bool = Field(..., description="存储是否成功")
    stored_count: int = Field(..., description="存储的记忆数量")
    stored_memories: List[dict] = Field(default_factory=list, description="存储的记忆内容")

class ListResponse(BaseModel):
    """列表响应模型"""
    memories: List[dict] = Field(default_factory=list, description="记忆列表（Edge 级别细节）")
    episodes: List[dict] = Field(default_factory=list, description="完整记忆列表（Episodic 原始故事）")
    count: int = Field(..., description="记忆数量")
    grouped: Optional[dict] = Field(None, description="按关系分组的历史视图")

class ClearResponse(BaseModel):
    """清空响应模型"""
    success: bool = Field(..., description="是否成功")
    cleared_count: int = Field(..., description="清空的记忆数量")
    error: Optional[str] = Field(None, description="错误信息")

# ==================== API 接口 ====================

@router.post("/{user_id}/retrieve", response_model=RetrieveResponse)
async def retrieve_memory(user_id: str, request: RetrieveRequest, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """
    判断是否需要检索 + 返回相关记忆
    """
    try:
        service = get_memory_service()
        result = await service.retrieve(user_id, request.query)
        return RetrieveResponse(**result)
    except Exception as e:
        logger.error(f"检索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{user_id}/store", response_model=SmartStoreResponse)
async def store_memory(user_id: str, request: SmartStoreRequest, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """
    判断是否需要存储 + 执行存储
    """
    try:
        service = get_memory_service()
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        result = await service.smart_store(user_id, messages)
        return SmartStoreResponse(**result)
    except Exception as e:
        logger.error(f"存储失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}", response_model=ListResponse)
async def list_memories(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """
    列出用户的所有记忆 (含历史时序分组)
    """
    try:
        service = get_memory_service()
        result = await service.get_all(user_id)

        # 适配新的返回结构
        if isinstance(result, dict) and "memories" in result:
            return ListResponse(
                memories=result.get("memories", []),
                episodes=result.get("episodes", []),
                count=result.get("count", len(result.get("memories", []))),
                grouped=result.get("grouped")
            )
        else:
            # 兼容旧的列表返回
            memories = result if isinstance(result, list) else []
            return ListResponse(memories=memories, episodes=[], count=len(memories), grouped=None)
    except Exception as e:
        logger.error(f"列表查询失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{user_id}", response_model=ClearResponse)
async def clear_memories(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """
    清空用户的所有记忆
    """
    try:
        service = get_memory_service()
        result = await service.clear(user_id)
        return ClearResponse(**result)
    except Exception as e:
        logger.error(f"清空失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class PolluteResponse(BaseModel):
    """污染响应模型"""
    success: bool = Field(..., description="是否成功")
    polluted_count: int = Field(..., description="注入的数量")

@router.post("/{user_id}/pollute", response_model=PolluteResponse)
async def pollute_memories(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """
    [DEBUG] 污染记忆库：一键注入10条无关随机数据
    """
    try:
        service = get_memory_service()
        result = await service.pollute_memory(user_id)
        return PolluteResponse(**result)
    except Exception as e:
        logger.error(f"污染失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

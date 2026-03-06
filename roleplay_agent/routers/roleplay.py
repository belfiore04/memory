"""
角色扮演模式路由
"""
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from langfuse import observe
from pydantic import BaseModel, Field

from shared.auth.auth import get_current_user
from shared.services.chat_log_service import ChatLogService
from roleplay_agent.services.roleplay_service import get_roleplay_service
from shared.utils.trace_service import TraceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/roleplay", tags=["Roleplay"])


# ==================== 服务依赖 ====================

_chat_log_service: Optional[ChatLogService] = None
_trace_service: Optional[TraceService] = None


def get_chat_log_service() -> ChatLogService:
    global _chat_log_service
    if _chat_log_service is None:
        _chat_log_service = ChatLogService()
    return _chat_log_service


def get_trace_service() -> TraceService:
    global _trace_service
    if _trace_service is None:
        _trace_service = TraceService()
    return _trace_service


# ==================== 数据模型 ====================

class SetCharacterRequest(BaseModel):
    content: str = Field(..., description="角色设定 Markdown 内容", min_length=1)



class InteractRequest(BaseModel):
    user_query: str = Field(..., description="用户输入消息", min_length=1, max_length=10000)


class InteractResponse(BaseModel):
    reply: str
    debug_info: Dict = Field(default_factory=dict)


class WorkspaceFileItem(BaseModel):
    filename: str
    size: int
    lines: int
    exists: bool


# ==================== API 端点 ====================

@router.post("/{user_id}/character")
async def set_character(
    user_id: str,
    request: SetCharacterRequest,
    current_user: dict = Depends(get_current_user),
):
    """直接设置角色设定并初始化 workspace。"""
    if current_user.get("id") != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    service = get_roleplay_service()
    try:
        workspace = service.init_character(user_id, request.content)
        return {"success": True, "workspace": str(workspace)}
    except Exception as e:
        logger.error(f"Error setting character: {e}")
        raise HTTPException(status_code=500, detail="角色设定失败")



@router.post("/{user_id}/interact", response_model=InteractResponse)
@observe(name="Roleplay Interaction")
async def interact(
    user_id: str,
    request: InteractRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    chat_log_service: ChatLogService = Depends(get_chat_log_service),
    trace_service: TraceService = Depends(get_trace_service),
):
    """
    主聊天端点。发送消息并获取角色回复。
    """
    if current_user.get("id") != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    service = get_roleplay_service()

    if not service.has_workspace(user_id):
        raise HTTPException(status_code=400, detail="请先选择角色")

    # 获取最近历史（从 ChatLogService，降序返回需反转）
    try:
        recent = chat_log_service.get_history(user_id, limit=100)
        history = [{"role": m["role"], "content": m["content"]} for m in reversed(recent)]
    except Exception:
        history = []

    try:
        result = await service.chat_interact(
            user_id=user_id,
            message=request.user_query,
            history=history,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    reply = result["reply"]
    workspace_dir = result["workspace_dir"]
    messages_snapshot = result["messages"]
    latency_ms = result["latency_ms"]

    # 持久化聊天记录
    try:
        chat_log_service.log_messages(
            user_id=user_id,
            messages=[
                {"role": "user", "content": request.user_query},
                {"role": "assistant", "content": reply},
            ],
            character_name="roleplay",
        )
    except Exception as e:
        logger.error(f"Failed to log chat: {e}")

    # 记录 trace
    langfuse_trace_id = None
    try:
        from langfuse import get_client as get_langfuse
        ctx = get_langfuse().get_current_trace()
        if ctx:
            langfuse_trace_id = ctx.id
    except Exception:
        pass

    trace_id = None
    try:
        trace_id = trace_service.record_trace(
            user_id=user_id,
            latency_ms=latency_ms,
            steps={"chat": latency_ms},
            prompt_snapshot="(see langfuse)",
            model_reply=reply,
            langfuse_trace_id=langfuse_trace_id,
        )
    except Exception as e:
        logger.error(f"Failed to record trace: {e}")

    # 后台启动异步 Agent 整理记忆
    background_tasks.add_task(
        service.run_async_memory_agent,
        messages_snapshot,
        workspace_dir,
    )

    return InteractResponse(
        reply=reply,
        debug_info={
            "trace_id": trace_id,
            "langfuse_trace_id": langfuse_trace_id,
            "latency": {"chat": latency_ms},
            "total_latency_ms": latency_ms,
        },
    )


@router.get("/{user_id}/workspace", response_model=List[WorkspaceFileItem])
async def get_workspace(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """列出 workspace 文件状态。"""
    if current_user.get("id") != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    service = get_roleplay_service()
    return service.get_workspace_files(user_id)


@router.get("/{user_id}/workspace/{filename}")
async def get_workspace_file(
    user_id: str,
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    """读取 workspace 中的某个文件。"""
    if current_user.get("id") != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    service = get_roleplay_service()
    content = service.get_file_content(user_id, filename)
    if content is None:
        raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")
    return {"filename": filename, "content": content}


@router.get("/{user_id}/notes")
async def get_notes(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """读取角色笔记。"""
    if current_user.get("id") != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    service = get_roleplay_service()
    return {"content": service.get_notes(user_id)}


@router.post("/{user_id}/workspace/reset")
async def reset_workspace(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """重置 workspace 记忆文件（保留 CHARACTER.md）。"""
    if current_user.get("id") != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    service = get_roleplay_service()
    service.reset(user_id)
    return {"success": True, "message": "Workspace 已重置"}

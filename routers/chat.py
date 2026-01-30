from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging
import json
import re

from services.memory_service import MemoryService
from services.context_service import ContextService
from services.profile_service import ProfileService
from services.chat_log_service import ChatLogService
from services.trace_service import TraceService
from services.feedback_service import FeedbackService
from services.trace_service import TraceService
from services.feedback_service import FeedbackService
from services.focus_service import FocusService
from agents.extraction_agent import ExtractionAgent
from agents.whisperer_agent import WhispererAgent
from schemas.common import MessageItem
from routers.auth import get_current_user
from datetime import datetime
import time
import os
from langfuse.openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# 独立的 AsyncOpenAI 客户端，用于聊天生成（不经过 Graphiti 的 JSON-only monkey patch）
_chat_llm_client: Optional[AsyncOpenAI] = None
def get_chat_llm_client() -> AsyncOpenAI:
    global _chat_llm_client
    if _chat_llm_client is None:
        _chat_llm_client = AsyncOpenAI(
            api_key=os.getenv("MINIMAX_API_KEY"),
            base_url="https://api.minimax.chat/v1",
        )
    return _chat_llm_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

# ==================== 服务初始化 (本地单例) ====================

_memory_service: Optional[MemoryService] = None
def get_memory_service() -> MemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service

_context_service: Optional[ContextService] = None
def get_context_service() -> ContextService:
    global _context_service
    if _context_service is None:
        _context_service = ContextService()
    return _context_service

_profile_service: Optional[ProfileService] = None
def get_profile_service() -> ProfileService:
    global _profile_service
    if _profile_service is None:
        _profile_service = ProfileService()
    return _profile_service

_extraction_agent: Optional[ExtractionAgent] = None
def get_extraction_agent() -> ExtractionAgent:
    global _extraction_agent
    if _extraction_agent is None:
        _extraction_agent = ExtractionAgent()
    return _extraction_agent

_chat_log_service: Optional[ChatLogService] = None
def get_chat_log_service() -> ChatLogService:
    global _chat_log_service
    if _chat_log_service is None:
        _chat_log_service = ChatLogService()
    return _chat_log_service

_trace_service: Optional[TraceService] = None
def get_trace_service() -> TraceService:
    global _trace_service
    if _trace_service is None:
        _trace_service = TraceService()
    return _trace_service

_feedback_service: Optional[FeedbackService] = None
def get_feedback_service() -> FeedbackService:
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = FeedbackService()
    return _feedback_service

_focus_service: Optional[FocusService] = None
def get_focus_service() -> FocusService:
    global _focus_service
    if _focus_service is None:
        _focus_service = FocusService()
    return _focus_service

_whisperer_agent: Optional[WhispererAgent] = None
def get_whisperer_agent() -> WhispererAgent:
    global _whisperer_agent
    if _whisperer_agent is None:
        _whisperer_agent = WhispererAgent()
    return _whisperer_agent

# ==================== 请求/响应模型 ====================

class ChatPrepareRequest(BaseModel):
    """Chat 准备请求 (不再需要 user_id)"""
    query: str = Field(..., description="用户查询内容")

class ChatCompleteRequest(BaseModel):
    """Chat 完成请求 (不再需要 user_id)"""
    messages: List[MessageItem] = Field(..., description="当前轮对话 [user, assistant]")
    virtual_date: Optional[str] = Field(None, description="虚拟日期 (YYYY-MM-DD)，用于调试模拟")

class ChatInteractRequest(BaseModel):
    """Chat 聚合交互请求 (替代 n8n)"""
    user_query: str = Field(..., description="用户输入")
    system_prompt: Optional[str] = Field(None, description="系统提示词模板 (可选)")
    virtual_date: Optional[str] = Field(None, description="虚拟日期 (YYYY-MM-DD)")

class ChatInteractResponse(BaseModel):
    """Chat 聚合交互响应"""
    reply: str
    debug_info: Dict[str, Any]

class FeedbackRequest(BaseModel):
    """反馈评分请求"""
    trace_id: str = Field(..., description="SQLite trace_id")
    langfuse_trace_id: Optional[str] = Field(None, description="Langfuse trace_id（可选）")
    score: int = Field(..., ge=1, le=5, description="评分 1-5")
    categories: Optional[List[str]] = Field(None, description="问题分类列表")
    comment: Optional[str] = Field(None, description="可选备注")

# ==================== Chat 聚合 API ====================

@router.post("/{user_id}/prepare")
async def chat_prepare(user_id: str, request: ChatPrepareRequest, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """
    聚合接口：LLM 回复前调用
    """
    try:
        # 1. 获取上下文
        context_service = get_context_service()
        context_result = context_service.get_context(user_id)
        
        # 2. 获取长期记忆
        memory_service = get_memory_service()
        memory_result = await memory_service.retrieve(user_id, request.query)
        
        # 3. 获取用户画像
        profile_service = get_profile_service()
        profile_slots = profile_service.get_all_slots(user_id)
        
        return {
            "context": {
                "summary": context_result.get("summary", ""),
                "history": context_result.get("history", []),
                "full_text": context_result.get("full_text", "")
            },
            "memory": {
                "should_retrieve": memory_result.get("should_retrieve", False),
                "reason": memory_result.get("reason", ""),
                "memories": memory_result.get("memories", []),
                "episodes": memory_result.get("episodes", [])
            },
            "profile": {
                "slots": profile_slots
            }
        }
    except Exception as e:
        logger.error(f"Chat prepare 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


from langfuse import observe, get_client

from fastapi import BackgroundTasks

async def _process_chat_background(
    user_id: str, 
    messages: List[Dict[str, str]], 
    virtual_date: Optional[str] = None, 
    trace_id: Optional[str] = None,
    context_service: Any = None,
    extraction_agent: Any = None,
    profile_service: Any = None,
    memory_service: Any = None,
    trace_service: Any = None,
    focus_service: Any = None,
    whisperer_agent: Any = None,
    langfuse_trace_id: Optional[str] = None
):
    """
    后台任务：处理对话分析、记忆提取和画像更新
    """
    # 构造 Trace Context 以连接主 Trace
    trace_ctx = {"trace_id": langfuse_trace_id} if langfuse_trace_id else None
    
    # 使用 start_as_current_span 确保后续 @observe (如 Graphiti) 能正确挂载 context
    with get_client().start_as_current_span(
        name="对话记忆整理",
        trace_context=trace_ctx
    ) as span:
        try:
            # 确保 trace 名称不被子 observation 覆盖
            get_client().update_current_trace(name="聊天")

            # 获取服务（如果未传入则使用默认，方便常规 API 调用）
            context_service = context_service or get_context_service()
            extraction_agent = extraction_agent or get_extraction_agent()
            profile_service = profile_service or get_profile_service()
            memory_service = memory_service or get_memory_service()
            trace_service = trace_service or get_trace_service()
            focus_service = focus_service or get_focus_service()
            whisperer_agent = whisperer_agent or get_whisperer_agent()
            
            logger.info(f"[Background] 开始处理对话分析 user_id={user_id}, trace_id={langfuse_trace_id}")
    
            
            # 0. 提取用户最新的 Query 和 Assistant 的完整回复
            user_query = ""
            assistant_reply = ""
            
            for msg in reversed(messages):
                if msg["role"] == "user" and not user_query:
                    user_query = msg["content"]
                elif msg["role"] == "assistant" and not assistant_reply:
                    assistant_reply = msg["content"]
                
                if user_query and assistant_reply:
                    break
            
            if not user_query:
                logger.warning("[Background] 未找到 User Query，跳过分析")
                return
    
            # 1. 解析 Assistant 回复
            inner_monologue = ""
            role_reply = ""
            
            if assistant_reply:
                try:
                    parsed = json.loads(assistant_reply)
                    if isinstance(parsed, dict):
                        inner_monologue = parsed.get("inner_monologue", "")
                        role_reply = parsed.get("reply", "")
                except (json.JSONDecodeError, TypeError):
                    monologue_match = re.search(r"【内心独白】\s*(.*?)\s*【回复】", assistant_reply, re.DOTALL)
                    reply_match = re.search(r"【回复】\s*(.*)", assistant_reply, re.DOTALL)
                    inner_monologue = monologue_match.group(1).strip() if monologue_match else ""
                    role_reply = reply_match.group(1).strip() if reply_match else ""
                    if not role_reply and not inner_monologue:
                        role_reply = assistant_reply
            
            # 2. 获取上下文摘要辅助分析
            context_data = context_service.get_context(user_id)
            # 注意：这里获取的 context 已经是包含当前最新消息的了（因为 update_context 已经在前台执行）
            # 但这对分析影响不大，甚至更好

            # 3. 记忆提取与存储（包含分析和graphiti存储）
            with get_client().start_as_current_span(name="记忆提取") as extraction_span:
                # 3.1 分析对话内容并存储到graphiti
                with get_client().start_as_current_span(name="分析对话内容") as analysis_span:
                    # 调用 ExtractionAgent（传入完整对话，包括角色回复）
                    analysis_result = extraction_agent.analyze_query(
                        user_id,
                        user_query,
                        assistant_reply=role_reply,  # 传入角色回复，用于提取角色创造的共同记忆
                    )

                    # [NEW] 提取完成后立即同步到 Trace (供前端回显)
                    memory_items = analysis_result.get("memory_items", [])
                    slot_updates = analysis_result.get("slot_updates", [])
                    recent_focus = analysis_result.get("recent_focus", [])

                    trace_updates = [m.get("content") for m in memory_items]
                    
                    # 将 recent_focus 也记入 trace 并同步到 profile
                    if recent_focus:
                        for focus in recent_focus:
                            trace_updates.append(f"近期关注: {focus.get('content')}")
                            # [MODIFY] 不再存入 Profile，而是存入 FocusService
                            if focus_service:
                                focus_service.add_focus(user_id, focus.get("content"))
                            
                    if trace_id and trace_updates:
                        # Manually update custom trace service (sqlite)
                         trace_service.update_trace_memories(trace_id, trace_updates)

                    if slot_updates:
                        # 将画像更新也作为"新记忆"的一类返回给前端 Trace，避免前端因 memory 为空而报错
                        for slot in slot_updates:
                            trace_updates.append(f"更新画像 [{slot['slot']}]: {slot['value']}")

                    if trace_id and trace_updates:
                        # Manually update custom trace service (sqlite)
                         trace_service.update_trace_memories(trace_id, trace_updates)

                    # 执行记忆存储到graphiti (在同一个"分析对话内容" span下)
                    if memory_items:
                        for item in memory_items:
                            await memory_service.add_memory_item(user_id, item.get("content"), item.get("type", "fact"))

                # 3.2 执行画像更新
                if slot_updates:
                    profile_service.batch_update(user_id, slot_updates)
            
            # 4. [NEW] 耳语者异步分析 (N+1 策略)
            with get_client().start_as_current_span(name="耳语者分析") as whisper_span:
                # 获取所需上下文
                # [MODIFY] 获取带时间信息的 focus 列表
                active_focus = focus_service.get_active_focus_with_time(user_id)
                current_profile = profile_service.get_all_slots(user_id)
                
                # 使用 context 的近期历史（包含摘要之后的多轮对话），而非只有当前一轮的 messages
                recent_history = context_data.get("history", [])

                # [NEW] 空载跳过逻辑：如果画像、焦点、历史均为空，则不激活耳语者
                if not active_focus and not current_profile and len(recent_history) <= 2:
                    logger.info(f"[Whisperer] 跳过分析 user_id={user_id}: 画像、焦点及历史均为空")
                    return

                # 确定当前时间 (优先使用 virtual_date)
                from datetime import datetime
                if virtual_date:
                    current_time_str = f"{virtual_date} {datetime.now().strftime('%H:%M:%S')}"
                else:
                    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                suggestion_result = whisperer_agent.create_suggestion(
                    user_id=user_id,
                    profile=current_profile,
                    active_focus=active_focus,
                    chat_summary=context_data.get("summary", ""),
                    chat_history=recent_history,
                    current_time=current_time_str
                )
                
                # [MODIFY] 解包返回值
                if suggestion_result:
                    suggestion, used_focus_id = suggestion_result
                    if suggestion:
                        focus_service.save_whisper_suggestion(user_id, suggestion)
                        
                        # [NEW] 如果使用了特定 focus，标记为已注入 (触发 12h 冷却)
                        if used_focus_id:
                            focus_service.mark_focus_injected(used_focus_id)
                            logger.info(f"[Whisperer] Focus {used_focus_id} 进入冷却期")
            
            logger.info(f"[Background] 分析完成 user_id={user_id}")
            
        except Exception as e:
            import traceback
            logger.error(f"[Background] 处理失败: {e}\n{traceback.format_exc()}")
            # 后台任务失败不影响主接口返回，但记录错误


@router.post("/{user_id}/complete")
@observe(name="Chat Complete API")
async def chat_complete(user_id: str, request: ChatCompleteRequest, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """
    聚合接口：LLM 回复后调用
    """
    try:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        logger.info(f"[ChatComplete] 收到请求 user_id={user_id}, msgs={len(messages)}, virtual_date={request.virtual_date}")
        
        # 1. 立即记录到 ChatLog (DB IO, fast)
        chat_log_service = get_chat_log_service()
        chat_log_service.log_messages(user_id, messages, virtual_date=request.virtual_date)
        
        # 2. 立即追加短期上下文 (SQLite IO, fast)
        context_service = get_context_service()
        context_service.append_message(user_id, messages)

        # 获取当前 Trace ID (由于 SDK 兼容性问题，暂时无法传递)
        # 获取当前 Trace ID (用于关联后台任务)
        try:
            current_trace_id = get_client().get_current_trace_id()
            logger.info(f"[ChatComplete] Current Trace ID: {current_trace_id}")
        except Exception as e:
            current_trace_id = None
            logger.warning(f"[ChatComplete] 无法获取当前 Trace ID: {e}")

        # 3. 将耗时的分析和记忆存储放入后台任务
        background_tasks.add_task(_process_chat_background, user_id, messages, request.virtual_date, trace_id=None, langfuse_trace_id=current_trace_id)
        
        return {"success": True}
    except Exception as e:
        logger.error(f"Chat complete 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/history")
async def get_chat_history(
    user_id: str,
    limit: int = Query(20, description="获取条数"),
    before_id: Optional[int] = Query(None, description="获取该ID之前的记录（分页用）"),
    current_user: dict = Depends(get_current_user)
):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """
    分页获取全量历史记录
    """
    try:
        service = get_chat_log_service()
        history = service.get_history(user_id, limit, before_id)
        return {
            "user_id": user_id,
            "count": len(history),
            "history": history
        }
    except Exception as e:
        logger.error(f"获取历史记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{user_id}/history")
async def clear_chat_history(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """
    清空用户所有历史记录
    """
    try:
        service = get_chat_log_service()
        success = service.clear_history(user_id)
        if success:
            return {"success": True, "message": f"用户 {user_id} 的历史记录已清空"}
        else:
            raise HTTPException(status_code=500, detail="清空失败")
    except Exception as e:
        logger.error(f"清空历史记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trace/{trace_id}")
async def get_chat_trace(trace_id: str, current_user: dict = Depends(get_current_user)):
    """获取单条 Trace 详情 (包含异步提取出的记忆)"""
    try:
        service = get_trace_service()
        trace = service.get_trace(trace_id)
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")
        
        # 权限校验
        if trace["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Forbidden")
            
        return {
            "trace_id": trace["trace_id"],
            "langfuse_trace_id": trace.get("langfuse_trace_id"),
            "latency_ms": trace["latency_ms"],
            "steps": json.loads(trace["steps"] or "{}"),
            "new_memories": json.loads(trace["new_memories"] or "[]"),
            "created_at": trace["created_at"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 Trace 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{user_id}/interact", response_model=ChatInteractResponse)
@observe(name="Chat Interaction")
async def chat_interact(
    user_id: str, 
    request: ChatInteractRequest, 
    background_tasks: BackgroundTasks, 
    current_user: dict = Depends(get_current_user),
    context_service = Depends(get_context_service),
    memory_service = Depends(get_memory_service),
    profile_service = Depends(get_profile_service),
    chat_log_service = Depends(get_chat_log_service),
    trace_service = Depends(get_trace_service),
    extraction_agent = Depends(get_extraction_agent),
    focus_service = Depends(get_focus_service),
    whisperer_agent = Depends(get_whisperer_agent)
):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    
    """
    聚合交互接口 (All-in-One): 取记忆 -> 拼 Prompt -> 调 LLM -> 存记忆
    替代 n8n 流程
    """
    start_time = time.time()
    steps_latency = {}
    
    try:
        # [Trace Name Fix] 强制更新 Trace Name，防止被后台任务覆盖
        get_client().update_current_trace(name="聊天")

        # 1. Prepare: 获取所有上下文
        t0 = time.time()
        
        # (a) Context
        context_data = context_service.get_context(user_id)
        
        # (b) Memory
        memory_result = await memory_service.retrieve(user_id, request.user_query)
        
        # (c) Profile
        profile_slots = profile_service.get_all_slots(user_id)
        
        # (d) Whisper Suggestion (N+1, reading from previous turn)
        whisper_suggestion = focus_service.get_latest_whisper(user_id)
        
        steps_latency["preparation"] = int((time.time() - t0) * 1000)
        
        # 2. Prompt Engineering (Strictly following n8n template)
        t0 = time.time()
        
        # 默认 System Prompt
        default_system_prompt = """
你是一个拥有长期记忆的 AI 伴侣。请根据提供的[过往记忆]、[用户资料]和[上下文]来回复用户。
风格要求：亲切、自然、简洁。
"""
        base_prompt = request.system_prompt if request.system_prompt else default_system_prompt
        
        # 拼装上下文块
        memory_block = ""
        if memory_result.get("memories"):
            memory_block = "【过往记忆】\\n" + "\\n".join([f"- {m['content']}" for m in memory_result["memories"]]) + "\\n"
            
        profile_block = ""
        if profile_slots:
            profile_block = "【用户资料】\\n" + "\\n".join([f"- {k}: {v}" for k, v in profile_slots.items()]) + "\\n"
            
        context_summary = f"【长期聊史】{context_data.get('summary')}\\n" if context_data.get('summary') else ""
        
        recent_history = ""
        if context_data.get("history"):
            recent_history = "【近期对话】\\n" + "\\n".join([f"{h['role']}: {h['content']}" for h in context_data["history"]])
            
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 添加时段描述
        hour = datetime.now().hour
        if 5 <= hour < 12:
            time_period = "上午"
        elif 12 <= hour < 14:
            time_period = "中午"
        elif 14 <= hour < 18:
            time_period = "下午"
        elif 18 <= hour < 22:
            time_period = "晚上"
        else:
            time_period = "深夜"
        current_time_str = f"{current_time_str} ({time_period})"
        
        # 耳语注入 block (放在 task 之前，让模型更好注意)
        whisper_block = ""
        if whisper_suggestion:
            whisper_block = f"\n<guidance>\n【耳语】{whisper_suggestion}\n</guidance>\n"
        
        # 最终 Prompt (基于 n8n XML 结构)
        final_system_prompt = f"""<role>
{base_prompt}
在此角色设定基础上，你必须严格按照特定格式输出：只输出回复内容字符串。
</role>


<context>
{memory_block}{profile_block}{context_summary}{recent_history}
</context>

<output_format>
严禁输出 Markdown 代码块标记（如 ```json），仅输出纯字符串。
</output_format>
{whisper_block}

<environment>
现在的时间是: {current_time_str}
</environment>

<task>
用户对你说：{request.user_query}
请根据上述要求生成回复：
</task>"""
        steps_latency["prompt_assembly"] = int((time.time() - t0) * 1000)

        # 3. LLM Generation（使用独立客户端，不经过 Graphiti JSON patch）
        t0 = time.time()
        messages = [
            {"role": "system", "content": final_system_prompt},
            {"role": "user", "content": request.user_query}
        ]

        with get_client().start_as_current_span(name="生成回复") as span:
            chat_client = get_chat_llm_client()
            chat_model = "M2-her"
            llm_response = await chat_client.chat.completions.create(
                model=chat_model,
                messages=messages,
                max_tokens=2048,
            )

            # 兼容 Langfuse AsyncOpenAI 包装器（返回 dict）和标准 OpenAI（返回 object）
            message = llm_response.choices[0].message
            if isinstance(message, dict):
                ai_reply = message.get("content", "")
            else:
                ai_reply = message.content or ""

            usage = llm_response.usage
            if isinstance(usage, dict):
                token_usage = {
                    "prompt": usage.get("prompt_tokens", 0),
                    "completion": usage.get("completion_tokens", 0),
                    "total": usage.get("total_tokens", 0),
                }
            else:
                token_usage = {
                    "prompt": usage.prompt_tokens if usage else 0,
                    "completion": usage.completion_tokens if usage else 0,
                    "total": usage.total_tokens if usage else 0,
                }

        steps_latency["llm_generation"] = int((time.time() - t0) * 1000)
        
        # 4. Post-Processing & Async Storage
        t0 = time.time()
        
        # (a) 立即存储 Logs & Context (确保下一轮对话能看到)
        chat_msgs = [
            {"role": "user", "content": request.user_query},
            {"role": "assistant", "content": ai_reply}
        ]
        chat_log_service.log_messages(user_id, chat_msgs, virtual_date=request.virtual_date)
        context_service.append_message(user_id, chat_msgs)
        
        steps_latency["post_processing"] = int((time.time() - t0) * 1000)
        total_latency = int((time.time() - start_time) * 1000)
        
        # 5. Record Trace (提前执行，以便 trace_id 可选传给后台任务)
        langfuse_trace_id = get_client().get_current_trace_id()

        trace_id = trace_service.record_trace(
            user_id=user_id,
            latency_ms=total_latency,
            steps=steps_latency,
            prompt_snapshot=final_system_prompt + f"\n\n[User]: {request.user_query}",
            model_reply=ai_reply,
            token_usage=token_usage,
            langfuse_trace_id=langfuse_trace_id
        )

        # (b) 触发后台深度分析 (Memory & Profile)
        background_tasks.add_task(
            _process_chat_background,
            user_id,
            chat_msgs,
            virtual_date=request.virtual_date,
            trace_id=trace_id,
            context_service=context_service,
            extraction_agent=extraction_agent,
            profile_service=profile_service,
            memory_service=memory_service,
            trace_service=trace_service,
            focus_service=focus_service,
            whisperer_agent=whisperer_agent,
            langfuse_trace_id=langfuse_trace_id
        )

        logger.info(f"[ChatInteract] Passed Trace ID to background: {langfuse_trace_id}")

        return {
            "reply": ai_reply,
            "debug_info": {
                "trace_id": trace_id,
                "langfuse_trace_id": langfuse_trace_id,
                "latency": steps_latency,
                "total_latency_ms": total_latency,
                "prompt_preview": final_system_prompt,
                "token_usage": token_usage,
                "whisper_consumed": whisper_suggestion # Debug info
            }
        }
        
    except Exception as e:
        logger.error(f"Chat Interact 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 反馈评分 API ====================

@router.get("/feedback/{feedback_id}")
async def get_feedback(
    feedback_id: str,
    current_user: dict = Depends(get_current_user),
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """查看单条反馈详情"""
    try:
        feedback = feedback_service.get_feedback(feedback_id)
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")
        if feedback["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Forbidden")
        return feedback
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询反馈失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{user_id}/feedback")
async def submit_feedback(
    user_id: str,
    request: FeedbackRequest,
    current_user: dict = Depends(get_current_user),
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """提交反馈评分"""
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    try:
        feedback_id = feedback_service.submit(
            user_id=user_id,
            trace_id=request.trace_id,
            score=request.score,
            categories=request.categories,
            comment=request.comment,
            langfuse_trace_id=request.langfuse_trace_id,
        )
        return {"feedback_id": feedback_id, "success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"提交反馈失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/feedback")
async def list_user_feedback(
    user_id: str,
    limit: int = Query(20, description="获取条数"),
    current_user: dict = Depends(get_current_user),
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """查看该用户最近的反馈"""
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    try:
        feedbacks = feedback_service.list_recent(user_id, limit)
        return {"user_id": user_id, "count": len(feedbacks), "feedbacks": feedbacks}
    except Exception as e:
        logger.error(f"查询反馈列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

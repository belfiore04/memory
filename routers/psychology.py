from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, timedelta
import logging

from services.chat_log_service import ChatLogService
from services.daily_summary_service import DailySummaryService
from services.profile_service import ProfileService
from agents.summary_agent import SummaryAgent
from agents.psychologist_agent import PsychologistAgent
from fastapi import Depends
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/psychology", tags=["Psychology"])

# ==================== 服务初始化 ====================

_chat_log_service: Optional[ChatLogService] = None
def get_chat_log_service() -> ChatLogService:
    global _chat_log_service
    if _chat_log_service is None:
        _chat_log_service = ChatLogService()
    return _chat_log_service

_daily_summary_service: Optional[DailySummaryService] = None
def get_daily_summary_service() -> DailySummaryService:
    global _daily_summary_service
    if _daily_summary_service is None:
        _daily_summary_service = DailySummaryService()
    return _daily_summary_service

_profile_service: Optional[ProfileService] = None
def get_profile_service() -> ProfileService:
    global _profile_service
    if _profile_service is None:
        _profile_service = ProfileService()
    return _profile_service

_summary_agent: Optional[SummaryAgent] = None
def get_summary_agent() -> SummaryAgent:
    global _summary_agent
    if _summary_agent is None:
        _summary_agent = SummaryAgent()
    return _summary_agent

_psychologist_agent: Optional[PsychologistAgent] = None
def get_psychologist_agent() -> PsychologistAgent:
    global _psychologist_agent
    if _psychologist_agent is None:
        _psychologist_agent = PsychologistAgent()
    return _psychologist_agent

# ==================== 请求模型 ====================

class TriggerSummaryRequest(BaseModel):
    """触发摘要请求"""
    date: Optional[str] = Field(None, description="目标日期 (YYYY-MM-DD)，默认昨天")

# ==================== 接口实现 ====================

@router.post("/{user_id}/trigger/summary")
async def trigger_summary(user_id: str, request: TriggerSummaryRequest, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """
    手动触发每日摘要生成
    """
    try:
        logger.info(f"[Psychology] 收到触发摘要请求: date={request.date}")
        if request.date:
            try:
                if len(request.date) == 8 and request.date[2] == '-': # Handle YY-MM-DD
                     target_date = date.fromisoformat(f"20{request.date}")
                else:
                     target_date = date.fromisoformat(request.date)
            except ValueError:
                 logger.error(f"[Psychology] 日期格式错误: {request.date}")
                 raise HTTPException(status_code=400, detail=f"日期格式错误，应为 YYYY-MM-DD，实际收到: {request.date}")
        else:
            target_date = date.today()
        
        logger.info(f"[Psychology] 手动触发摘要 user_id={user_id}, date={target_date}")
        
        chat_log_service = get_chat_log_service()
        logs = chat_log_service.get_daily_logs(user_id, target_date)
        
        if not logs:
            return {"success": False, "message": f"用户 {user_id} 在 {target_date} 没有对话记录"}
        
        summary_agent = get_summary_agent()
        summary_result = summary_agent.summarize(logs)
        
        daily_summary_service = get_daily_summary_service()
        import json
        daily_summary_service.save_summary(
            user_id=user_id,
            summary_date=target_date,
            summary_text=summary_result.get("summary", ""),
            key_events=json.dumps(summary_result.get("key_events", []), ensure_ascii=False),
            emotional_changes=summary_result.get("emotional_changes", ""),
            personal_info=json.dumps(summary_result.get("personal_info", []), ensure_ascii=False)
        )
        
        return {
            "success": True,
            "user_id": user_id,
            "date": target_date.isoformat(),
            "summary": summary_result
        }
    except Exception as e:
        logger.error(f"[Psychology] 摘要触发失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{user_id}/trigger/analysis")
async def trigger_analysis(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """
    手动触发心理分析 (分析该用户的所有摘要)
    """
    try:
        logger.info(f"[Psychology] 手动触发分析 user_id={user_id}")
        
        daily_summary_service = get_daily_summary_service()
        summaries = daily_summary_service.get_recent_summaries(user_id, days=365)
        
        if not summaries:
            return {"success": False, "message": f"用户 {user_id} 没有摘要记录"}
        
        combined_summary = "\n\n".join([f"[{s['date']}] {s['summary']}" for s in summaries])
        
        psychologist_agent = get_psychologist_agent()
        analysis_result = psychologist_agent.analyze_daily_summary(user_id, combined_summary)
        
        slot_updates = analysis_result.get("slot_updates", [])
        if slot_updates:
            profile_service = get_profile_service()
            profile_service.batch_update(user_id, slot_updates)
        
        return {
            "success": True,
            "user_id": user_id,
            "summaries_analyzed": len(summaries),
            "analysis": analysis_result,
            "updated_slots": len(slot_updates)
        }
    except Exception as e:
        logger.error(f"[Psychology] 分析触发失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/summary")
async def get_summaries(
    user_id: str,
    days: int = Query(7, description="查询最近 N 天"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    current_user: dict = Depends(get_current_user)
):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """查询用户的每日摘要"""
    try:
        daily_summary_service = get_daily_summary_service()
        if start_date and end_date:
            summaries = daily_summary_service.get_summaries_by_range(
                user_id, date.fromisoformat(start_date), date.fromisoformat(end_date)
            )
        else:
            summaries = daily_summary_service.get_recent_summaries(user_id, days)
        return {"user_id": user_id, "count": len(summaries), "summaries": summaries}
    except Exception as e:
        logger.error(f"查询摘要失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/traits")
async def get_traits(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """查询用户的心理特质槽位"""
    try:
        profile_service = get_profile_service()
        all_slots = profile_service.get_all_slots(user_id)
        psychology_slots = ["core_beliefs", "values", "defense_mechanisms", "attachment_style"]
        traits = {k: all_slots.get(k, "") for k in psychology_slots}
        return {"user_id": user_id, "traits": traits}
    except Exception as e:
        logger.error(f"查询心理特质失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{user_id}/clear")
async def clear_psychology_data(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own data")
    """清空用户的所有心理分析数据"""
    try:
        daily_summary_service = get_daily_summary_service()
        daily_summary_service.clear_summaries(user_id)
        
        profile_service = get_profile_service()
        psychology_slots = ["core_beliefs", "values", "defense_mechanisms", "attachment_style"]
        slot_updates = [{"slot": slot, "value": ""} for slot in psychology_slots]
        profile_service.batch_update(user_id, slot_updates)
        
        return {"success": True, "message": f"用户 {user_id} 的心理数据已清空"}
    except Exception as e:
        logger.error(f"清空心理数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

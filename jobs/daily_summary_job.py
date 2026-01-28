"""
每日心理分析定时任务
每天凌晨运行，分析所有用户的当日对话，提取心理特质
"""
import logging
import json
from datetime import date, timedelta
from typing import List, Dict

from services.chat_log_service import ChatLogService
from services.daily_summary_service import DailySummaryService
from services.profile_service import ProfileService
from agents.summary_agent import SummaryAgent
from agents.psychologist_agent import PsychologistAgent

logger = logging.getLogger(__name__)


def run_daily_analysis():
    """执行每日心理分析"""
    logger.info("[DailyJob] 开始每日心理分析任务...")
    
    # 分析昨天的日志
    yesterday = date.today() - timedelta(days=1)
    logger.info(f"[DailyJob] 目标日期: {yesterday}")
    
    try:
        # 初始化服务和 Agent
        chat_log_service = ChatLogService()
        daily_summary_service = DailySummaryService()
        profile_service = ProfileService()
        summary_agent = SummaryAgent()
        psychologist_agent = PsychologistAgent()
        
        # 获取所有用户
        user_ids = chat_log_service.get_all_user_ids()
        logger.info(f"[DailyJob] 需分析用户数: {len(user_ids)}")
        
        for user_id in user_ids:
            try:
                # 1. 获取昨日对话
                logs = chat_log_service.get_daily_logs(user_id, yesterday)
                if not logs:
                    logger.info(f"[DailyJob] 用户 {user_id} 昨日无对话，跳过")
                    continue
                
                logger.info(f"[DailyJob] 用户 {user_id} 对话条数: {len(logs)}")
                
                # 2. 生成摘要
                summary_result = summary_agent.summarize(logs)
                summary_text = summary_result.get("summary", "")
                
                if not summary_text.strip() or summary_text == "无对话记录":
                    logger.info(f"[DailyJob] 用户 {user_id} 摘要为空，跳过分析")
                    continue
                
                # 3. 存储摘要
                daily_summary_service.save_summary(
                    user_id=user_id,
                    summary_date=yesterday,
                    summary_text=summary_text,
                    key_events=json.dumps(summary_result.get("key_events", []), ensure_ascii=False),
                    emotional_changes=summary_result.get("emotional_changes", ""),
                    personal_info=json.dumps(summary_result.get("personal_info", []), ensure_ascii=False)
                )
                
                # 4. 心理分析
                analysis_result = psychologist_agent.analyze_daily_summary(user_id, summary_text)
                
                # 5. 更新画像
                slot_updates = analysis_result.get("slot_updates", [])
                if slot_updates:
                    logger.info(f"[DailyJob] 用户 {user_id} 检测到 {len(slot_updates)} 个心理特质更新")
                    profile_service.batch_update(user_id, slot_updates)
                
                logger.info(f"[DailyJob] 完成用户 {user_id} 的心理分析")
            
            except Exception as e:
                logger.error(f"[DailyJob] 用户 {user_id} 分析出错: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"[DailyJob] 任务执行失败: {str(e)}")

    logger.info("[DailyJob] 每日心理分析任务结束")


if __name__ == "__main__":
    # 手动测试入口
    run_daily_analysis()

import os
import json
import logging
import asyncio
from typing import Dict, List
from unittest.mock import MagicMock

# 模拟环境
os.environ["ABILITY_MODEL"] = "qwen-max"

from services.focus_service import FocusService
from services.profile_service import ProfileService
from agents.whisperer_agent import WhispererAgent

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_focus_and_whisperer_flow():
    user_id = "test_user_flow"
    
    # 1. 初始化服务
    focus_service = FocusService()
    whisperer_agent = WhispererAgent()
    profile_service = ProfileService() # 会创建 profile.db
    
    # 清理旧数据
    try:
        conn = focus_service._init_db() or sqlite3.connect(focus_service.db_path) 
        # Hacky clean for test
        os.remove(focus_service.db_path)
    except:
        pass
    focus_service = FocusService() # Re-init clean db

    logger.info(">>> STEP 1: 第一轮对话 (用户提到找工作)")
    user_query_1 = "哎，最近找工作好难啊，投了好多简历都没回音。"
    assistant_reply_1 = "别灰心，现在行情确实一般，多改改简历试试？"
    
    # A. 模拟 Extraction 提取到 Focus
    logger.info("[模拟] ExtractionAgent 提取到 '找工作'")
    focus_service.add_focus(user_id, "正在找工作，有些受挫")
    
    # B. 模拟 Background Task: Whisperer 分析
    logger.info("[模拟] WhispererAgent 正在分析第一轮对话...")
    
    chat_history_1 = [
        {"role": "user", "content": user_query_1},
        {"role": "assistant", "content": assistant_reply_1}
    ]
    active_focus = focus_service.get_active_focus(user_id)
    profile = {} # 假设为空
    
    # Mock LLM response to avoid real API call cost/dependency in test script if needed, 
    # but let's try real call if environment allows. If fails, fallback or mock.
    # Here we assume real call is possible or we mock it. Let's mock for stability.
    whisperer_agent.client.chat.completions.create = MagicMock()
    mock_ret = MagicMock()
    mock_ret.choices[0].message.content = json.dumps({
        "should_intervene": True,
        "suggestion": "用户感到受挫，下一轮请主动询问他具体是哪个方向的岗位，并给予具体的行业鼓励。"
    })
    whisperer_agent.client.chat.completions.create.return_value = mock_ret
    
    suggestion = whisperer_agent.create_suggestion(user_id, profile, active_focus, "", chat_history_1)
    if suggestion:
        logger.info(f"生成建议: {suggestion}")
        focus_service.save_whisper_suggestion(user_id, suggestion)
    else:
        logger.error("未能生成建议")

    logger.info(">>> STEP 2: 第二轮对话 (用户闲聊)")
    
    # C. 模拟主流程：读取 Whisper 建议
    whisper_consumed = focus_service.get_latest_whisper(user_id)
    
    if whisper_consumed == "用户感到受挫，下一轮请主动询问他具体是哪个方向的岗位，并给予具体的行业鼓励。":
        logger.info("PASS: 成功读取到上一轮的耳语建议")
    else:
        logger.error(f"FAIL: 读取建议不匹配: {whisper_consumed}")

    # D. 再次尝试读取（应该为空，因为已消费）
    whisper_consumed_again = focus_service.get_latest_whisper(user_id)
    if whisper_consumed_again is None:
        logger.info("PASS: 建议已消费，不再重复读取")
    else:
        logger.error("FAIL: 建议未被消费")

if __name__ == "__main__":
    import sqlite3
    test_focus_and_whisperer_flow()

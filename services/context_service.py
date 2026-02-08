#!/usr/bin/env python3
"""
上下文服务模块
提供基于用户的上下文管理，支持自动概括和历史记录维护
"""

import os
import json
import sqlite3
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from langfuse import observe

logger = logging.getLogger(__name__)

class ContextService:
    """上下文服务类 - 管理用户摘要和最近历史"""
    
    def __init__(self):
        """初始化上下文服务"""
        load_dotenv()  # 确保加载环境变量
        logger.info("初始化上下文服务")
        
        # 初始化 DB
        self.mem0_path = os.path.abspath("./.mem0")
        if not os.path.exists(self.mem0_path):
            os.makedirs(self.mem0_path)
        self.db_path = os.path.join(self.mem0_path, "context.db")
        self._init_db()
        
        # 初始化 OpenAI 客户端 (使用 DashScope API)
        dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        dashscope_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.client = OpenAI(api_key=dashscope_api_key, base_url=dashscope_base_url)
        self.llm_model = os.getenv("SPEED_MODEL", "qwen-flash")
        
        # 配置
        self.max_history_rounds = 50  # 触发概括的对话轮数阈值（1轮 = user + assistant 各1条消息）
        self.session_timeout_hours = 3  # 会话超时时间（小时），超过后自动清空摘要
        
    def _init_db(self):
        """初始化数据库表 (使用 user_id 替代 conversation_id)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # 注意：字段名改为 user_id
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_context (
                    user_id TEXT PRIMARY KEY,
                    summary TEXT,
                    recent_messages TEXT,
                    updated_at DATETIME
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"上下文DB初始化失败: {str(e)}")
            raise

    def get_context(self, user_id: str) -> Dict:
        """
        获取上下文：
        1. 如果会话超时（3小时），自动清空摘要
        2. 如果历史记录过长，会自动触发概括
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT summary, recent_messages, updated_at FROM user_context WHERE user_id = ?", 
                (user_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return {
                    "summary": "",
                    "history": [],
                    "full_text": ""
                }
            
            summary = row[0] or ""
            recent_messages = json.loads(row[1]) if row[1] else []
            updated_at_str = row[2]
            
            # [NEW] 检查会话是否超时
            session_expired = False
            if updated_at_str and summary:  # 只有有摘要时才需要检查
                try:
                    if isinstance(updated_at_str, str):
                        updated_at = datetime.fromisoformat(updated_at_str)
                    else:
                        updated_at = updated_at_str
                    
                    if datetime.now() - updated_at > timedelta(hours=self.session_timeout_hours):
                        session_expired = True
                        logger.info(f"[Context] 会话超时（>{self.session_timeout_hours}h），清空摘要 user_id={user_id}")
                except Exception as e:
                    logger.warning(f"[Context] 解析 updated_at 失败: {e}")
            
            if session_expired:
                # 清空摘要，保留 history
                summary = ""
                cursor.execute(
                    "UPDATE user_context SET summary = '' WHERE user_id = ?",
                    (user_id,)
                )
                conn.commit()
            
            # 计算轮数（每轮 = user + assistant 各1条，共2条消息）
            current_rounds = len(recent_messages) // 2
            logger.info(f"[Context] user_id={user_id}, rounds={current_rounds}")
            
            # 检查是否需要概括
            if current_rounds >= self.max_history_rounds:
                logger.info(f"[Context] 触发概括 (轮数 {current_rounds} >= {self.max_history_rounds})")
                new_summary, remaining_messages = self._summarize(summary, recent_messages)
                
                # 更新 DB
                cursor.execute(
                    """
                    UPDATE user_context 
                    SET summary = ?, recent_messages = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (new_summary, json.dumps(remaining_messages, ensure_ascii=False), datetime.now(), user_id)
                )
                conn.commit()
                
                summary = new_summary
                recent_messages = remaining_messages
            
            # 格式化输出
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in recent_messages])
            full_text = ""
            if summary:
                full_text += f"前情提要:\n{summary}\n\n"
            if history_text:
                full_text += f"最近对话:\n{history_text}"
                
            return {
                "summary": summary,
                "history": recent_messages,
                "full_text": full_text
            }
            
        finally:
            conn.close()

    def append_message(self, user_id: str, messages: List[Dict]):
        """追加新消息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT summary, recent_messages FROM user_context WHERE user_id = ?", 
                (user_id,)
            )
            row = cursor.fetchone()
            
            if row:
                current_messages = json.loads(row[1]) if row[1] else []
                current_messages.extend(messages)
                cursor.execute(
                    "UPDATE user_context SET recent_messages = ?, updated_at = ? WHERE user_id = ?",
                    (json.dumps(current_messages, ensure_ascii=False), datetime.now(), user_id)
                )
            else:
                cursor.execute(
                    "INSERT INTO user_context (user_id, summary, recent_messages, updated_at) VALUES (?, ?, ?, ?)",
                    (user_id, "", json.dumps(messages, ensure_ascii=False), datetime.now())
                )
            
            conn.commit()
            logger.info(f"[Context] 追加消息成功 user_id={user_id}, count={len(messages)}")
            
        except Exception as e:
            logger.error(f"[Context] 追加消息失败: {str(e)}")
            raise
        finally:
            conn.close()

    @observe(name="概括短期上下文")
    def _summarize(self, current_summary: str, messages: List[Dict]) -> Tuple[str, List[Dict]]:
        """
        调用 LLM 进行概括
        """
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        
        prompt = f"""请对以下对话历史进行简要概括。重点关注：                                                                                                     
1. 讨论了什么话题                                                                                                                            
2. 用户的情绪状态和需求（是想倾诉、求建议、还是闲聊）                                                                                        
3. 有没有敏感/被回避的话题                                                                                                                   
4. 对话是怎么结束的（自然结束、话题转移、用户情绪变化
        
{f'已有摘要：{current_summary}' if current_summary else ''}

新增对话：
{history_text}

请输出一个新的、合并后的摘要，包含关键信息（如用户意图、重要事实、讨论话题），字数控制在300字以内。
直接输出摘要内容。"""

        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "你是一个专业的对话摘要助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                name="Summarizer LLM"
            )
            
            new_summary = response.choices[0].message.content.strip()
            logger.info(f"[Context] 概括完成: {new_summary[:50]}...")
            
            # 保留最后1轮对话（最后2条消息），避免历史完全为空
            remaining = messages[-2:] if len(messages) >= 2 else messages
            return new_summary, remaining
            
        except Exception as e:
            logger.error(f"[Context] LLM 概括失败: {str(e)}")
            return current_summary, messages

    def clear_context(self, user_id: str):
        """清空用户的上下文"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM user_context WHERE user_id = ?", (user_id,))
            conn.commit()
            logger.info(f"[Context] 上下文已清空 user_id={user_id}")
        except Exception as e:
            logger.error(f"[Context] 清空上下文失败: {str(e)}")
            raise
        finally:
            conn.close()

    def clear_summary(self, user_id: str):
        """仅清空用户的摘要，保留对话历史"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE user_context SET summary = '' WHERE user_id = ?", (user_id,))
            conn.commit()
            logger.info(f"[Context] 摘要已清空 user_id={user_id}")
        except Exception as e:
            logger.error(f"[Context] 清空摘要失败: {str(e)}")
            raise
        finally:
            conn.close()


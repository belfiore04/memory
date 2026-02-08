"""
聊天记录服务
负责持久化存储所有用户与模型的对话，供心理 Agent 分析使用
"""
import sqlite3
import json
import os
import logging
from datetime import datetime, date
from typing import List, Dict

logger = logging.getLogger(__name__)

class ChatLogService:
    """聊天记录持久化服务"""
    
    def __init__(self, db_path: str = "./.mem0/chat_logs.db"):
        self.mem0_path = os.path.abspath("./.mem0")
        if not os.path.exists(self.mem0_path):
            os.makedirs(self.mem0_path)
        self.db_path = os.path.join(self.mem0_path, "chat_logs.db")
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建基础表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 检查并添加 character_name 列
            cursor.execute("PRAGMA table_info(chat_logs)")
            columns = [info[1] for info in cursor.fetchall()]
            
            if "character_name" not in columns:
                cursor.execute("ALTER TABLE chat_logs ADD COLUMN character_name TEXT")
                logger.info("[ChatLog] Added column: character_name")
                
            if "character_persona" not in columns:
                cursor.execute("ALTER TABLE chat_logs ADD COLUMN character_persona TEXT")
                logger.info("[ChatLog] Added column: character_persona")

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_date 
                ON chat_logs(user_id, created_at)
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[ChatLog] 初始化 DB 失败: {str(e)}")
            raise
    
    def log_message(self, user_id: str, role: str, content: str, created_at: str = None, character_name: str = None, character_persona: str = None):
        """
        记录单条消息
        
        Args:
            user_id: 用户ID
            role: 消息角色 (user/assistant)
            content: 消息内容
            created_at: 可选，指定创建时间 (格式: YYYY-MM-DD HH:MM:SS)，用于调试模拟
            character_name: 当时生效的 AI 名字
            character_persona: 当时生效的人设
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # [FIX] 如果未指定时间，使用本地时间而非 UTC (DB DEFAULT)
            if not created_at:
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute(
                """
                INSERT INTO chat_logs (user_id, role, content, created_at, character_name, character_persona) 
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, role, content, created_at, character_name, character_persona)
            )
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[ChatLog] 记录消息失败: {str(e)}")
    
    def log_messages(self, user_id: str, messages: List[Dict[str, str]], virtual_date: str = None, character_name: str = None, character_persona: str = None):
        """
        批量记录消息
        
        Args:
            user_id: 用户ID
            messages: 消息列表
            virtual_date: 可选，虚拟日期 (格式: YYYY-MM-DD)，用于调试模拟
            character_name: AI 名字
            character_persona: AI 人设
        """
        created_at = None
        if virtual_date:
            # 在虚拟日期当天的中午 12:00 写入
            created_at = f"{virtual_date} 12:00:00"
        
        for msg in messages:
            self.log_message(user_id, msg["role"], msg["content"], created_at, character_name, character_persona)

    def get_daily_logs(self, user_id: str, target_date: date) -> List[Dict]:
        """获取指定日期的聊天记录"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # SQLite 的 date 函数处理 timestamp
            start_date_str = target_date.strftime("%Y-%m-%d 00:00:00")
            end_date_str = target_date.strftime("%Y-%m-%d 23:59:59")
            
            cursor.execute(
                """
                SELECT role, content, created_at, character_name, character_persona 
                FROM chat_logs 
                WHERE user_id = ? AND created_at BETWEEN ? AND ?
                ORDER BY created_at ASC
                """,
                (user_id, start_date_str, end_date_str)
            )
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "role": r[0], 
                    "content": r[1], 
                    "created_at": r[2],
                    "character_name": r[3],
                    "character_persona": r[4]
                } 
                for r in rows
            ]
        except Exception as e:
            logger.error(f"[ChatLog] 获取日志失败: {str(e)}")
            return []
    
    def get_all_user_ids(self) -> List[str]:
        """获取所有有记录的用户ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT user_id FROM chat_logs")
            rows = cursor.fetchall()
            conn.close()
            return [r[0] for r in rows]
        except Exception as e:
            logger.error(f"[ChatLog] 获取用户ID失败: {str(e)}")
            return []

    def get_history(self, user_id: str, limit: int = 20, before_id: int = None) -> List[Dict]:
        """
        分页获取聊天历史 (降序)
        
        Args:
            user_id: 用户ID
            limit: 每页条数
            before_id: 获取该ID之前的记录（用于分页）
            
        Returns:
            List[Dict]: 消息列表 (包含 id, role, content, created_at)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = "SELECT id, role, content, created_at, character_name, character_persona FROM chat_logs WHERE user_id = ?"
            params = [user_id]
            
            if before_id:
                query += " AND id < ?"
                params.append(before_id)
                
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "id": r[0],
                    "role": r[1],
                    "content": r[2],
                    "created_at": r[3],
                    "character_name": r[4],
                    "character_persona": r[5]
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"[ChatLog] 获取历史失败: {str(e)}")
            return []
            
    def get_stats(self) -> Dict[str, int]:
        """获取系统统计信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 1. 今日日期字符串 (本地)
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            # 2. 今日活跃用户数 (发送过消息的去重用户)
            cursor.execute(
                "SELECT COUNT(DISTINCT user_id) FROM chat_logs WHERE created_at LIKE ?",
                (f"{today_str}%",)
            )
            today_active_users = cursor.fetchone()[0] or 0
            
            # 3. 今日用户聊天轮数 (role='user' 的消息总数)
            cursor.execute(
                "SELECT COUNT(*) FROM chat_logs WHERE role = 'user' AND created_at LIKE ?",
                (f"{today_str}%",)
            )
            today_chat_rounds = cursor.fetchone()[0] or 0
            
            conn.close()

            return {
                "today_active_users": today_active_users,
                "today_chat_rounds": today_chat_rounds
            }
        except Exception as e:
            logger.error(f"[ChatLog] 获取统计失败: {str(e)}")
            return {
                "today_active_users": 0,
                "today_chat_rounds": 0
            }

    def get_stats_since(self, since_at: str) -> Dict[str, int]:
        """获取指定时间之后的统计信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 1. 活跃用户数 (DISTINCT user_id)
            cursor.execute(
                "SELECT COUNT(DISTINCT user_id) FROM chat_logs WHERE created_at >= ?",
                (since_at,)
            )
            active_users = cursor.fetchone()[0] or 0
            
            # 2. 用户聊天轮数 (role='user' 的消息总数)
            cursor.execute(
                "SELECT COUNT(*) FROM chat_logs WHERE role = 'user' AND created_at >= ?",
                (since_at,)
            )
            chat_rounds = cursor.fetchone()[0] or 0
            
            conn.close()
            
            return {
                "active_users": active_users,
                "chat_rounds": chat_rounds
            }
        except Exception as e:
            logger.error(f"[ChatLog] 获取时段统计信息失败: {str(e)}")
            return {
                "active_users": 0,
                "chat_rounds": 0
            }

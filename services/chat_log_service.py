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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_date 
                ON chat_logs(user_id, created_at)
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[ChatLog] 初始化 DB 失败: {str(e)}")
            raise
    
    def log_message(self, user_id: str, role: str, content: str, created_at: str = None):
        """
        记录单条消息
        
        Args:
            user_id: 用户ID
            role: 消息角色 (user/assistant)
            content: 消息内容
            created_at: 可选，指定创建时间 (格式: YYYY-MM-DD HH:MM:SS)，用于调试模拟
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if created_at:
                # 使用指定时间（调试模式）
                cursor.execute(
                    "INSERT INTO chat_logs (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, role, content, created_at)
                )
            else:
                # 使用当前时间（正常模式）
                cursor.execute(
                    "INSERT INTO chat_logs (user_id, role, content) VALUES (?, ?, ?)",
                    (user_id, role, content)
                )
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[ChatLog] 记录消息失败: {str(e)}")
    
    def log_messages(self, user_id: str, messages: List[Dict[str, str]], virtual_date: str = None):
        """
        批量记录消息
        
        Args:
            user_id: 用户ID
            messages: 消息列表
            virtual_date: 可选，虚拟日期 (格式: YYYY-MM-DD)，用于调试模拟
        """
        created_at = None
        if virtual_date:
            # 在虚拟日期当天的中午 12:00 写入
            created_at = f"{virtual_date} 12:00:00"
        
        for msg in messages:
            self.log_message(user_id, msg["role"], msg["content"], created_at)

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
                SELECT role, content, created_at 
                FROM chat_logs 
                WHERE user_id = ? AND created_at BETWEEN ? AND ?
                ORDER BY created_at ASC
                """,
                (user_id, start_date_str, end_date_str)
            )
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {"role": r[0], "content": r[1], "created_at": r[2]} 
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
            
            query = "SELECT id, role, content, created_at FROM chat_logs WHERE user_id = ?"
            params = [user_id]
            
            if before_id:
                query += " AND id < ?"
                params.append(before_id)
                
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            conn.close()
            
            # 结果需要反转为时间正序 (旧 -> 新) 方便前端展示
            # 但这里返回降序数据，前端收到后再 reverse 或者 prepend 也可以
            # 为了接口一致性，这里保持 DB 查出来的顺序 (降序: 最新 -> 最旧)
            return [
                {
                    "id": r[0],
                    "role": r[1],
                    "content": r[2],
                    "created_at": r[3]
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"[ChatLog] 获取历史失败: {str(e)}")
            return []
            
    def clear_history(self, user_id: str) -> bool:
        """清空用户的聊天历史"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_logs WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            logger.info(f"[ChatLog] 已清空用户 {user_id} 的历史记录")
            return True
        except Exception as e:
            logger.error(f"[ChatLog] 清空历史失败: {str(e)}")
            return False

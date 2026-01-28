"""
每日摘要服务
负责存储和查询用户的每日对话摘要
"""
import sqlite3
import os
import logging
from datetime import date, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class DailySummaryService:
    """每日摘要存储服务"""
    
    def __init__(self, db_path: str = "./.mem0/psychology.db"):
        self.mem0_path = os.path.abspath("./.mem0")
        if not os.path.exists(self.mem0_path):
            os.makedirs(self.mem0_path)
        self.db_path = os.path.join(self.mem0_path, "psychology.db")
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    summary_date DATE NOT NULL,
                    summary_text TEXT NOT NULL,
                    key_events TEXT,
                    emotional_changes TEXT,
                    personal_info TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, summary_date)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_summary_user_date 
                ON daily_summaries(user_id, summary_date)
            """)
            conn.commit()
            conn.close()
            logger.info("[DailySummary] 数据库初始化完成")
        except Exception as e:
            logger.error(f"[DailySummary] 初始化 DB 失败: {str(e)}")
            raise
    
    def save_summary(self, user_id: str, summary_date: date, summary_text: str,
                     key_events: str = "", emotional_changes: str = "", 
                     personal_info: str = "") -> bool:
        """
        保存每日摘要
        
        Args:
            user_id: 用户ID
            summary_date: 摘要日期
            summary_text: 摘要正文
            key_events: 关键事件（JSON 字符串）
            emotional_changes: 情绪变化
            personal_info: 个人信息（JSON 字符串）
        
        Returns:
            是否保存成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 使用 INSERT OR REPLACE 支持更新
            cursor.execute("""
                INSERT OR REPLACE INTO daily_summaries 
                (user_id, summary_date, summary_text, key_events, emotional_changes, personal_info)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, summary_date.isoformat(), summary_text, 
                  key_events, emotional_changes, personal_info))
            
            conn.commit()
            conn.close()
            logger.info(f"[DailySummary] 保存摘要成功 user_id={user_id}, date={summary_date}")
            return True
        except Exception as e:
            logger.error(f"[DailySummary] 保存摘要失败: {str(e)}")
            return False
    
    def get_summary(self, user_id: str, summary_date: date) -> Optional[Dict]:
        """获取指定日期的摘要"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT summary_text, key_events, emotional_changes, personal_info, created_at
                FROM daily_summaries
                WHERE user_id = ? AND summary_date = ?
            """, (user_id, summary_date.isoformat()))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    "date": summary_date.isoformat(),
                    "summary": row[0],
                    "key_events": row[1],
                    "emotional_changes": row[2],
                    "personal_info": row[3],
                    "created_at": row[4]
                }
            return None
        except Exception as e:
            logger.error(f"[DailySummary] 获取摘要失败: {str(e)}")
            return None
    
    def get_recent_summaries(self, user_id: str, days: int = 7) -> List[Dict]:
        """获取最近 N 天的摘要"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 为了支持虚拟日期测试，将结束日期由今天改为未来7天（或者更远），避免未来的摘要被过滤
            end_date = date.today() + timedelta(days=30)
            start_date = date.today() - timedelta(days=days)
            
            cursor.execute("""
                SELECT summary_date, summary_text, key_events, emotional_changes, personal_info
                FROM daily_summaries
                WHERE user_id = ? AND summary_date >= ?
                ORDER BY summary_date DESC
            """, (user_id, start_date.isoformat()))
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "date": r[0],
                    "summary": r[1],
                    "key_events": r[2],
                    "emotional_changes": r[3],
                    "personal_info": r[4]
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"[DailySummary] 获取最近摘要失败: {str(e)}")
            return []
    
    def get_summaries_by_range(self, user_id: str, start_date: date, end_date: date) -> List[Dict]:
        """获取指定日期范围的摘要"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT summary_date, summary_text, key_events, emotional_changes, personal_info
                FROM daily_summaries
                WHERE user_id = ? AND summary_date BETWEEN ? AND ?
                ORDER BY summary_date DESC
            """, (user_id, start_date.isoformat(), end_date.isoformat()))
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "date": r[0],
                    "summary": r[1],
                    "key_events": r[2],
                    "emotional_changes": r[3],
                    "personal_info": r[4]
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"[DailySummary] 获取日期范围摘要失败: {str(e)}")
            return []

    def clear_summaries(self, user_id: str) -> bool:
        """清空用户的所有摘要记录"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM daily_summaries WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            logger.info(f"[DailySummary] 已清空用户 {user_id} 的所有摘要")
            return True
        except Exception as e:
            logger.error(f"[DailySummary] 清空摘要失败: {str(e)}")
            return False

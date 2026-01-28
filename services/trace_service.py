import sqlite3
import json
import os
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class TraceService:
    """全链路追踪服务 (用于替代 n8n 的执行日志)"""
    
    def __init__(self, db_path: str = "./.mem0/traces.db"):
        self.mem0_path = os.path.abspath("./.mem0")
        if not os.path.exists(self.mem0_path):
            os.makedirs(self.mem0_path)
        self.db_path = os.path.join(self.mem0_path, "traces.db")
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    latency_ms INTEGER DEFAULT 0,
                    steps TEXT, -- JSON: 各阶段耗时
                    prompt_snapshot TEXT, -- 完整 Prompt
                    model_reply TEXT, -- 模型原始回复
                    token_usage TEXT, -- JSON: token 用量
                    new_memories TEXT, -- JSON: 新提取的记忆列表
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_created
                ON traces(user_id, created_at)
            """)
            # 迁移：添加 langfuse_trace_id 列（如果不存在）
            try:
                cursor.execute("ALTER TABLE traces ADD COLUMN langfuse_trace_id TEXT")
            except sqlite3.OperationalError:
                pass  # 列已存在
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[TraceService] 初始化 DB 失败: {str(e)}")
            raise

    def record_trace(
        self,
        user_id: str,
        latency_ms: int,
        steps: Dict[str, int],
        prompt_snapshot: str,
        model_reply: str,
        token_usage: Optional[Dict[str, int]] = None,
        langfuse_trace_id: Optional[str] = None
    ) -> str:
        """
        记录一条完整的执行 Trace
        返回 trace_id
        """
        trace_id = str(uuid.uuid4())
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO traces
                (trace_id, user_id, latency_ms, steps, prompt_snapshot, model_reply, token_usage, langfuse_trace_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    user_id,
                    latency_ms,
                    json.dumps(steps, ensure_ascii=False),
                    prompt_snapshot,
                    model_reply,
                    json.dumps(token_usage or {}, ensure_ascii=False),
                    langfuse_trace_id
                )
            )
            
            conn.commit()
            conn.close()
            return trace_id
        except Exception as e:
            logger.error(f"[TraceService] 记录 Trace 失败: {str(e)}")
            return ""

    def update_trace_memories(self, trace_id: str, memories: list):
        """更新 Trace 记录中的新提取记忆"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE traces SET new_memories = ? WHERE trace_id = ?",
                (json.dumps(memories, ensure_ascii=False), trace_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[TraceService] 更新 Trace 记忆失败: {str(e)}")

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """获取单条 Trace 详情"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM traces WHERE trace_id = ?", (trace_id,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"[TraceService] 获取 Trace {trace_id} 失败: {str(e)}")
            return None

    def get_recent_traces(self, user_id: str, limit: int = 10) -> list:
        """获取最近的 Traces"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT * FROM traces 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
                """, 
                (user_id, limit)
            )
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"[TraceService] 获取 Traces 失败: {str(e)}")
            return []

import sqlite3
import json
import os
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# 问题分类定义
FEEDBACK_CATEGORIES = {
    "memory_forget": "忘记了我想让他记住的东西",
    "model_ooc": "模型不说人话/抽风/ooc",
    "other": "其他",
}



class FeedbackService:
    """用户反馈评分服务：存储到本地 SQLite 并推送到 Langfuse"""

    def __init__(self, db_path: str = "./.mem0/feedback.db"):
        self.mem0_path = os.path.abspath("./.mem0")
        if not os.path.exists(self.mem0_path):
            os.makedirs(self.mem0_path)
        self.db_path = os.path.join(self.mem0_path, "feedback.db")
        self._init_db()

    def _init_db(self):
        """初始化反馈表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    langfuse_trace_id TEXT,
                    score INTEGER NOT NULL,
                    categories TEXT,
                    comment TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_user
                ON feedback(user_id, created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_trace
                ON feedback(trace_id)
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[FeedbackService] 初始化 DB 失败: {str(e)}")
            raise

    def submit(
        self,
        user_id: str,
        trace_id: str,
        score: int,
        categories: Optional[List[str]] = None,
        comment: Optional[str] = None,
        langfuse_trace_id: Optional[str] = None,
    ) -> str:
        """
        提交反馈：存 SQLite + 推 Langfuse score
        返回 feedback_id
        """
        if not 1 <= score <= 5:
            raise ValueError("score 必须在 1-5 之间")

        # 校验分类
        if categories:
            for cat in categories:
                if cat not in FEEDBACK_CATEGORIES:
                    raise ValueError(f"未知的分类: {cat}")

        feedback_id = str(uuid.uuid4())

        # 1. 存入 SQLite
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO feedback
                (feedback_id, user_id, trace_id, langfuse_trace_id, score, categories, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id,
                    user_id,
                    trace_id,
                    langfuse_trace_id,
                    score,
                    json.dumps(categories or [], ensure_ascii=False),
                    comment,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[FeedbackService] 存储反馈失败: {str(e)}")
            raise

        # 2. 推送到 Langfuse
        if langfuse_trace_id:
            self._push_to_langfuse(langfuse_trace_id, score, categories, comment)

        return feedback_id

    def _push_to_langfuse(
        self,
        langfuse_trace_id: str,
        score: int,
        categories: Optional[List[str]],
        comment: Optional[str],
    ):
        """推送 score 到 Langfuse Dashboard"""
        try:
            from langfuse import get_client

            client = get_client()

            # (a) 数值评分
            # 将分类合并到 Comment 中显示
            full_comment = comment or ""
            if categories:
                cat_labels = [FEEDBACK_CATEGORIES.get(c, c) for c in categories]
                prefix = f"【反馈分类】{', '.join(cat_labels)}"
                if full_comment:
                    full_comment = f"{prefix}\n{full_comment}"
                else:
                    full_comment = prefix

            client.create_score(
                trace_id=langfuse_trace_id,
                name="user_feedback",
                value=score,
                comment=full_comment,
            )

            logger.info(
                f"[FeedbackService] 已推送 Langfuse score: trace={langfuse_trace_id}, score={score}"
            )
        except Exception as e:
            # Langfuse 推送失败不影响本地存储
            logger.warning(f"[FeedbackService] 推送 Langfuse 失败（不影响本地存储）: {str(e)}")

    def get_feedback(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        """获取单条反馈"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM feedback WHERE feedback_id = ?", (feedback_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                result = dict(row)
                result["categories"] = json.loads(result["categories"] or "[]")
                return result
            return None
        except Exception as e:
            logger.error(f"[FeedbackService] 获取反馈失败: {str(e)}")
            return None

    def get_by_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """根据 trace_id 获取关联的反馈列表"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM feedback WHERE trace_id = ? ORDER BY created_at DESC",
                (trace_id,),
            )
            rows = cursor.fetchall()
            conn.close()
            results = []
            for row in rows:
                r = dict(row)
                r["categories"] = json.loads(r["categories"] or "[]")
                results.append(r)
            return results
        except Exception as e:
            logger.error(f"[FeedbackService] 按 trace 查询反馈失败: {str(e)}")
            return []

    def list_recent(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户最近的反馈列表"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM feedback
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            rows = cursor.fetchall()
            conn.close()
            results = []
            for row in rows:
                r = dict(row)
                r["categories"] = json.loads(r["categories"] or "[]")
                results.append(r)
            return results
        except Exception as e:
            logger.error(f"[FeedbackService] 查询反馈列表失败: {str(e)}")
            return []

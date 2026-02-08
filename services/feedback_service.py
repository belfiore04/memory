import sqlite3
import json
import os
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# 问题分类定义 (分组管理)
FEEDBACK_GROUPS = {
    "chat": {
        "label": "对话质量",
        "categories": {
            "model_ooc": "模型不说人话/抽风/ooc",
            "memory_forget": "忘记了我想让他记住的东西",
            "other": "其他",
        }
    },
    "retrieval": {
        "label": "记忆召回",
        "categories": {
            "retrieval_bad_result": "没有想起正确的记忆",
            "other": "其他"
        }
    },
    "extraction": {
        "label": "记忆提取",
        "categories": {
            "memory_incomplete": "记住的信息不全",
            "memory_error": "记住了错误的信息",
            "memory_redundant": "记住了多余/没用的信息",
            "other": "其他",
        }
    }
}

# 扁平化的分类映射，用于快速校验和兼容
def _get_flat_categories() -> Dict[str, str]:
    flat = {}
    for group in FEEDBACK_GROUPS.values():
        flat.update(group["categories"])
    return flat

FEEDBACK_CATEGORIES = _get_flat_categories()

# 反向映射：Label -> Key (用于稳健兼容)
FEEDBACK_LABEL_TO_KEY = {v: k for k, v in FEEDBACK_CATEGORIES.items()}



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

            # 兼容旧数据库：添加 feedback_group 列
            cursor.execute("PRAGMA table_info(feedback)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'feedback_group' not in columns:
                cursor.execute("ALTER TABLE feedback ADD COLUMN feedback_group TEXT DEFAULT 'chat'")
                logger.info("已添加 feedback_group 列到 feedback 表")

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[FeedbackService] 初始化 DB 失败: {str(e)}")
            raise

    def get_metadata(self) -> Dict[str, Any]:
        """获取分类元数据供前端拉取"""
        return FEEDBACK_GROUPS

    def submit(
        self,
        user_id: str,
        trace_id: str,
        score: int,
        feedback_group: str = "chat",
        categories: Optional[List[str]] = None,
        comment: Optional[str] = None,
        langfuse_trace_id: Optional[str] = None,
    ) -> str:
        """
        提交反馈：存 SQLite + 推 Langfuse score
        返回 feedback_id

        Args:
            feedback_group: 反馈类型 - "chat" / "retrieval" / "extraction"
        """
        if not 1 <= score <= 5:
            raise ValueError("score 必须在 1-5 之间")

        if feedback_group not in FEEDBACK_GROUPS:
            raise ValueError(f"无效的 feedback_group: {feedback_group}，必须是 {list(FEEDBACK_GROUPS.keys())}")

        # 校验并归一化分类 (Key-based)
        normalized_categories = []
        if categories:
            for cat in categories:
                # 1. 如果本身就是合法的 Key，直接使用
                if cat in FEEDBACK_CATEGORIES:
                    normalized_categories.append(cat)
                # 2. 如果是 Label，自动转为 Key (稳健兼容)
                elif cat in FEEDBACK_LABEL_TO_KEY:
                    key = FEEDBACK_LABEL_TO_KEY[cat]
                    logger.info(f"[FeedbackService] 自动映射 Label '{cat}' -> Key '{key}'")
                    normalized_categories.append(key)
                # 3. 未知分类
                else:
                    raise ValueError(f"未知的分类: {cat}")

        feedback_id = str(uuid.uuid4())

        # 1. 存入 SQLite
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO feedback
                (feedback_id, user_id, trace_id, langfuse_trace_id, score, feedback_group, categories, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id,
                    user_id,
                    trace_id,
                    langfuse_trace_id,
                    score,
                    feedback_group,
                    json.dumps(normalized_categories, ensure_ascii=False),
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
            self._push_to_langfuse(langfuse_trace_id, feedback_group, score, normalized_categories, comment)

        return feedback_id

    def _push_to_langfuse(
        self,
        langfuse_trace_id: str,
        feedback_group: str,
        score: int,
        categories: Optional[List[str]],
        comment: Optional[str],
    ):
        """
        推送 score 到 Langfuse Dashboard

        方案1：用不同的 name 区分反馈类型
        - 主评分: {group}_feedback (NUMERIC 1-5)
        - 分类标签: 每个分类单独一条 CATEGORICAL score
        """
        try:
            from langfuse import get_client

            client = get_client()

            # (a) 主评分 - 按 feedback_group 区分 name
            score_name = f"{feedback_group}_feedback"  # 如 "chat_feedback", "retrieval_feedback"

            client.create_score(
                trace_id=langfuse_trace_id,
                name=score_name,
                value=score,
                comment=comment,
            )
            logger.info(
                f"[FeedbackService] 已推送主评分: trace={langfuse_trace_id}, name={score_name}, score={score}"
            )

            # (b) 分类标签 - 每个分类单独一条 CATEGORICAL score
            if categories:
                for cat_key in categories:
                    cat_label = FEEDBACK_CATEGORIES.get(cat_key, cat_key)
                    client.create_score(
                        trace_id=langfuse_trace_id,
                        name=cat_key,  # 如 "memory_error", "retrieval_bad_result"
                        value=cat_label,  # 中文 label 作为值
                        data_type="CATEGORICAL",
                    )
                    logger.info(
                        f"[FeedbackService] 已推送分类标签: name={cat_key}, value={cat_label}"
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

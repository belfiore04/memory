#!/usr/bin/env python3
"""
Focus Service Module
负责管理用户的短期关注点 (recent_focus) 和耳语者建议 (whisper_suggestions)。
"""

import os
import sqlite3
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

# 默认 TTL（天数）：无明确截止日期的关注点的有效期
# 默认 TTL（天数）：无明确截止日期的关注点的有效期
DEFAULT_FOCUS_TTL_DAYS = 14
# 注入冷却时间（小时）：防止同一关注点频繁注入
INJECTION_COOLDOWN_HOURS = 12

logger = logging.getLogger(__name__)

class FocusService:
    """短期关注与耳语者服务"""
    
    def __init__(self):
        self.mem0_path = os.path.abspath("./.mem0")
        if not os.path.exists(self.mem0_path):
            os.makedirs(self.mem0_path)
        self.db_path = os.path.join(self.mem0_path, "focus.db")
        self._init_db()
        
    def _init_db(self):
        """初始化数据库表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 1. 用户短期关注表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_focus (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT DEFAULT 'active', -- active, archived
                    expected_date TEXT,  -- 明确的截止日期 (YYYY-MM-DD)，可选
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """)
            
            # 检查并添加 expected_date 列（兼容旧数据库）
            cursor.execute("PRAGMA table_info(user_focus)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'expected_date' not in columns:
                cursor.execute("ALTER TABLE user_focus ADD COLUMN expected_date TEXT")
                logger.info("已添加 expected_date 列到 user_focus 表")

            if 'last_injected_at' not in columns:
                cursor.execute("ALTER TABLE user_focus ADD COLUMN last_injected_at DATETIME")
                logger.info("已添加 last_injected_at 列到 user_focus 表")
            
            # 2. 耳语者建议表 (N+1 轮机制)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whisper_suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    suggestion TEXT NOT NULL, -- 存储 JSON 或 纯文本建议
                    is_consumed INTEGER DEFAULT 0,
                    created_at DATETIME
                )
            """)
            
            conn.commit()
            conn.close()
            logger.info("Focus 数据库初始化成功")
        except Exception as e:
            logger.error(f"Focus 数据库初始化失败: {str(e)}")
            raise

    # ========================== Focus Management ==========================
    
    def add_focus(self, user_id: str, content: str, expected_date: str = None) -> bool:
        """
        添加新的关注点
        - 如果已存在 active 的相同内容，则刷新 updated_at（保持活跃）
        - 如果不存在，则新增
        
        Args:
            user_id: 用户ID
            content: 关注点内容
            expected_date: 明确的截止日期 (YYYY-MM-DD 格式)，可选
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            now = datetime.now()
            
            # 检查是否已存在
            cursor.execute(
                "SELECT id, expected_date FROM user_focus WHERE user_id = ? AND content = ? AND status = 'active'",
                (user_id, content)
            )
            existing = cursor.fetchone()
            
            if existing:
                # 已存在：刷新 updated_at，如果传入了新的 expected_date 也更新
                existing_id = existing[0]
                if expected_date:
                    cursor.execute(
                        "UPDATE user_focus SET updated_at = ?, expected_date = ? WHERE id = ?",
                        (now, expected_date, existing_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE user_focus SET updated_at = ? WHERE id = ?",
                        (now, existing_id)
                    )
                conn.commit()
                logger.info(f"刷新现有关注点: {content[:30]}...")
                return True  # 改为返回 True 表示刷新成功
            else:
                # 不存在：新增
                cursor.execute(
                    "INSERT INTO user_focus (user_id, content, expected_date, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, content, expected_date, now, now)
                )
                conn.commit()
                logger.info(f"添加新关注点: {content[:30]}...")
                return True
        except Exception as e:
            logger.error(f"添加关注点失败: {str(e)}")
            return False
        finally:
            conn.close()

    def get_active_focus(self, user_id: str) -> List[str]:
        """获取用户当前所有 active 的关注点（简单版，仅返回内容）"""
        focus_list = self.get_active_focus_with_time(user_id)
        return [f["content"] for f in focus_list]
    
    def get_active_focus_with_time(self, user_id: str) -> List[Dict]:
        """
        获取用户当前所有未过期的 active 关注点（带时间信息）
        自动过滤:
        1. 已过期的关注点
        2. 处于冷却期（12小时内已注入过）的关注点
        
        Returns:
            [{"id": 1, "content": ..., "recorded_at": ..., "expected_date": ...}, ...]
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 增加查询 id 和 last_injected_at
            cursor.execute(
                "SELECT id, content, expected_date, created_at, updated_at, last_injected_at FROM user_focus WHERE user_id = ? AND status = 'active' ORDER BY created_at DESC",
                (user_id,)
            )
            rows = cursor.fetchall()
            
            today = datetime.now().date()
            now = datetime.now()
            result = []
            
            for row in rows:
                f_id, content, expected_date, created_at, updated_at, last_injected_at = row
                
                # 1. 判断是否过期
                is_expired = False
                if expected_date:
                    try:
                        exp_date = datetime.strptime(expected_date, "%Y-%m-%d").date()
                        is_expired = today > exp_date + timedelta(days=1)
                    except ValueError:
                        pass
                else:
                    try:
                        if isinstance(created_at, str):
                            created = datetime.fromisoformat(created_at).date()
                        else:
                            created = created_at.date() if hasattr(created_at, 'date') else today
                        is_expired = today > created + timedelta(days=DEFAULT_FOCUS_TTL_DAYS)
                    except:
                        pass
                
                if is_expired:
                    continue

                # 2. 判断是否冷却中 (12小时)
                if last_injected_at:
                    try:
                        if isinstance(last_injected_at, str):
                            injected_time = datetime.fromisoformat(last_injected_at)
                        else:
                            injected_time = last_injected_at
                        
                        if now < injected_time + timedelta(hours=INJECTION_COOLDOWN_HOURS):
                            # logger.debug(f"关注点 '{content}' 处于冷却中，跳过")
                            continue
                    except:
                        pass

                result.append({
                    "id": f_id,
                    "content": content,
                    "recorded_at": str(created_at)[:10] if created_at else None,
                    "expected_date": expected_date
                })
            
            return result
        finally:
            conn.close()

    def mark_focus_injected(self, focus_id: int) -> bool:
        """标记某个关注点已被注入（更新 last_injected_at）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            now = datetime.now()
            cursor.execute(
                "UPDATE user_focus SET last_injected_at = ? WHERE id = ?",
                (now, focus_id)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"标记关注点注入失败: {str(e)}")
            return False
        finally:
            conn.close()
            
    def archive_focus(self, user_id: str, content: str) -> bool:
        """归档关注点（不再关注）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            now = datetime.now()
            cursor.execute(
                "UPDATE user_focus SET status = 'archived', updated_at = ? WHERE user_id = ? AND content = ?",
                (now, user_id, content)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ========================== Whisper Management ==========================

    def save_whisper_suggestion(self, user_id: str, suggestion: str):
        """保存耳语者对下一轮的建议"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 策略：为了避免堆积，可以先标记旧的未读消息已过期？
            # 或者简单点，chat 接口只取最后一条。
            # 这里只负责存。
            now = datetime.now()
            cursor.execute(
                "INSERT INTO whisper_suggestions (user_id, suggestion, created_at) VALUES (?, ?, ?)",
                (user_id, suggestion, now)
            )
            conn.commit()
        except Exception as e:
            logger.error(f"保存耳语建议失败: {str(e)}")
        finally:
            conn.close()

    def get_latest_whisper(self, user_id: str) -> Optional[str]:
        """
        获取并消费（标记为已读）最新的一条耳语建议
        只返回一条最新的且未消费的建议。
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 1. Get latest unconsumed
            cursor.execute(
                "SELECT id, suggestion FROM whisper_suggestions WHERE user_id = ? AND is_consumed = 0 ORDER BY created_at DESC LIMIT 1",
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            suggestion_id, suggestion = row
            
            # 2. Mark as consumed
            cursor.execute(
                "UPDATE whisper_suggestions SET is_consumed = 1 WHERE id = ?",
                (suggestion_id,)
            )
            conn.commit()
            
            return suggestion
        except Exception as e:
            logger.error(f"获取耳语建议失败: {str(e)}")
            return None
        finally:
            conn.close()

    def clear_all_focus(self, user_id: str) -> bool:
        """清空用户所有活跃的关注点"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 1. Archive focus
            cursor.execute(
                "UPDATE user_focus SET status = 'archived', updated_at = ? WHERE user_id = ? AND status = 'active'",
                (datetime.now(), user_id)
            )
            # 2. Clear pending whispers (mark as consumed)
            cursor.execute(
                "UPDATE whisper_suggestions SET is_consumed = 1 WHERE user_id = ? AND is_consumed = 0",
                (user_id,)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"清空关注点失败: {str(e)}")
            return False
        finally:
            conn.close()

    def peek_latest_whisper(self, user_id: str) -> Optional[Dict]:
        """
        仅查看最新的未消费耳语建议（不消费）
        返回字典包含 suggestion 和 created_at，如果没有则返回 None。
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT suggestion, created_at, is_consumed FROM whisper_suggestions WHERE user_id = ? AND is_consumed = 0 ORDER BY created_at DESC LIMIT 1",
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                "suggestion": row[0],
                "created_at": row[1],
                "is_consumed": bool(row[2])
            }
        except Exception as e:
            logger.error(f"查看耳语建议失败: {str(e)}")
            return None
        finally:
            conn.close()

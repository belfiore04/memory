#!/usr/bin/env python3
"""
用户画像服务模块

提供用户画像槽位的存储、检索、抽取和更新功能。
"""

import os
import json
import sqlite3
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

from schemas.profile_schema import (
    SLOT_SCHEMA, 
    get_extraction_prompt, 
    get_merge_judgment_prompt,
    get_slots_by_category
)

logger = logging.getLogger(__name__)


class ProfileService:
    """用户画像服务类"""
    
    def __init__(self):
        """初始化画像服务"""
        load_dotenv()
        logger.info("初始化用户画像服务")
        
        # 初始化 DB
        self.mem0_path = os.path.abspath("./.mem0")
        if not os.path.exists(self.mem0_path):
            os.makedirs(self.mem0_path)
        self.db_path = os.path.join(self.mem0_path, "profile.db")
        self._init_db()
        
        # 初始化 OpenAI 客户端 (使用 DashScope API)
        dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        dashscope_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.client = OpenAI(api_key=dashscope_api_key, base_url=dashscope_base_url)
        self.llm_model = os.getenv("SPEED_MODEL", "qwen-flash")
    
    def _init_db(self):
        """初始化数据库表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 用户画像表：每个用户一行，slots 存为 JSON
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    user_id TEXT PRIMARY KEY,
                    slots TEXT,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """)
            
            conn.commit()
            conn.close()
            logger.info(f"画像数据库初始化成功: {self.db_path}")
        except Exception as e:
            logger.error(f"画像数据库初始化失败: {str(e)}")
            raise
    
    def get_all_slots(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户的所有槽位
        
        Returns:
            {"nickname": "小明", "occupation": "程序员", ...}
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT slots FROM user_profile WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            
            if not row or not row[0]:
                return {}
            
            return json.loads(row[0])
        finally:
            conn.close()
    
    def get_profile_prompt(self, user_id: str) -> str:
        """
        生成用于 system prompt 的画像文本
        
        Returns:
            格式化的画像文本，按类别分组
        """
        slots = self.get_all_slots(user_id)
        
        if not slots:
            return ""
        
        # 按类别分组
        categories = get_slots_by_category()
        lines = ["## 用户画像"]
        
        for category, slot_keys in categories.items():
            category_items = []
            for key in slot_keys:
                if key in slots and slots[key]:
                    slot_info = SLOT_SCHEMA[key]
                    value = slots[key]
                    # 列表类型格式化
                    if isinstance(value, list):
                        value = "、".join(value)
                    category_items.append(f"- {slot_info['description']}: {value}")
            
            if category_items:
                lines.append(f"\n### {category}")
                lines.extend(category_items)
        
        # 如果只有标题没有内容，返回空
        if len(lines) == 1:
            return ""
        
        return "\n".join(lines)
    
    def extract_slots(self, user_id: str, messages: List[Dict[str, str]]) -> Dict:
        """
        从对话中抽取槽位信息并更新画像
        
        Args:
            user_id: 用户ID
            messages: 对话列表 [{"role": "user", "content": "..."}]
        
        Returns:
            {
                "extracted": {"nickname": "小明", ...},
                "updated_slots": ["nickname", "occupation"],
                "success": True
            }
        """
        logger.info(f"[Profile] 开始抽取槽位 user_id={user_id}")
        
        # 1. 调用 LLM 抽取槽位
        conversation = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        extraction_prompt = get_extraction_prompt()
        
        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": extraction_prompt},
                    {"role": "user", "content": f"对话内容：\n{conversation}"}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content.strip()
            logger.info(f"[Profile] LLM 抽取结果: {result_text}")
            
            # 解析 JSON
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            
            extracted = json.loads(result_text)
            
            if not extracted:
                return {"extracted": {}, "updated_slots": [], "success": True}
            
            # 2. 合并到现有画像
            updated_slots = self._merge_slots(user_id, extracted)
            
            return {
                "extracted": extracted,
                "updated_slots": updated_slots,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"[Profile] 槽位抽取失败: {str(e)}")
            return {"extracted": {}, "updated_slots": [], "success": False, "error": str(e)}
    
    def _merge_slots(self, user_id: str, new_slots: Dict[str, Any]) -> List[str]:
        """
        根据合并策略将新槽位合并到现有画像
        
        Returns:
            更新的槽位 key 列表
        """
        current_slots = self.get_all_slots(user_id)
        updated_keys = []
        
        for key, new_value in new_slots.items():
            if key not in SLOT_SCHEMA:
                logger.warning(f"[Profile] 未知槽位: {key}")
                continue
            
            slot_info = SLOT_SCHEMA[key]
            strategy = slot_info["merge_strategy"]
            old_value = current_slots.get(key)
            
            if old_value is None:
                # 新槽位，直接设置
                current_slots[key] = new_value
                updated_keys.append(key)
            elif strategy == "replace":
                # 覆盖
                current_slots[key] = new_value
                updated_keys.append(key)
            elif strategy == "append":
                # 追加到列表
                if not isinstance(current_slots[key], list):
                    current_slots[key] = [current_slots[key]] if current_slots[key] else []
                if isinstance(new_value, list):
                    for v in new_value:
                        if v not in current_slots[key]:
                            current_slots[key].append(v)
                            updated_keys.append(key)
                elif new_value not in current_slots[key]:
                    current_slots[key].append(new_value)
                    updated_keys.append(key)
            elif strategy == "llm_judge":
                # LLM 判断如何合并
                merged_value = self._llm_merge(key, str(old_value), str(new_value))
                if merged_value != old_value:
                    current_slots[key] = merged_value
                    updated_keys.append(key)
        
        # 保存到数据库
        self._save_slots(user_id, current_slots)
        
        return list(set(updated_keys))  # 去重
    
    def _llm_merge(self, slot_key: str, old_value: str, new_value: str) -> str:
        """调用 LLM 判断如何合并值"""
        prompt = get_merge_judgment_prompt(slot_key, old_value, new_value)
        
        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "你是一个用户画像更新助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=100
            )
            
            result_text = response.choices[0].message.content.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            
            result = json.loads(result_text)
            return result.get("value", new_value)
            
        except Exception as e:
            logger.error(f"[Profile] LLM 合并判断失败: {str(e)}")
            # 降级：使用新值
            return new_value
    
    def _save_slots(self, user_id: str, slots: Dict[str, Any]):
        """保存槽位到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT user_id FROM user_profile WHERE user_id = ?",
                (user_id,)
            )
            exists = cursor.fetchone() is not None
            
            slots_json = json.dumps(slots, ensure_ascii=False)
            now = datetime.now()
            
            if exists:
                cursor.execute(
                    "UPDATE user_profile SET slots = ?, updated_at = ? WHERE user_id = ?",
                    (slots_json, now, user_id)
                )
            else:
                cursor.execute(
                    "INSERT INTO user_profile (user_id, slots, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (user_id, slots_json, now, now)
                )
            
            conn.commit()
            logger.info(f"[Profile] 槽位已保存 user_id={user_id}")
        finally:
            conn.close()
    
    def update_slot(self, user_id: str, key: str, value: Any) -> Dict:
        """
        手动更新单个槽位
        
        Returns:
            {"success": True, "key": key, "value": value}
        """
        if key not in SLOT_SCHEMA:
            return {"success": False, "error": f"未知槽位: {key}"}
        
        current_slots = self.get_all_slots(user_id)
        current_slots[key] = value
        self._save_slots(user_id, current_slots)
        
        return {"success": True, "key": key, "value": value}

    def batch_update(self, user_id: str, updates: List[Dict[str, Any]]) -> Dict:
        """
        批量更新槽位 (用于 Analysis Agent 结果的应用)

        Args:
            user_id: 用户ID
            updates: [{"slot": "key", "value": "val", "evidence": "..."}]

        Returns:
            {"success": True, "updated_count": int, "errors": []}
        """
        current_slots = self.get_all_slots(user_id)
        updated_count = 0
        errors = []

        for update in updates:
            key = update.get("slot")
            value = update.get("value")

            # 过滤空值 - 不允许写入空字符串或空列表
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, list) and (not value or all(not v for v in value)):
                continue

            if not key or key not in SLOT_SCHEMA:
                errors.append(f"无效槽位: {key}")
                continue
                
            # 这里简化处理：直接应用更新（Analysis Agent 已经做过提取了）
            # 如果需要合并逻辑，可以复用 _merge_slots 的部分逻辑，
            # 但针对 extraction agent 的结果，通常认为是最新的、具体的观察。
            
            slot_info = SLOT_SCHEMA[key]
            strategy = slot_info["merge_strategy"]
            
            # 简单处理：如果是 list 类型的 append，如果是单值的 replace
            # 也可以复用 _merge_slots 里的逻辑，但要构造成 dict 传进去
            
            # 为了保持一致性，我们构造一个 dict 调用 _merge_slots
            # 但 _merge_slots 有 LLM 判断，这里 Analysis Agent 已经是很强的 LLM 了
            # 我们尽量直接应用，减少额外开销
            
            if strategy == "append":
                if not isinstance(current_slots.get(key), list):
                    current_slots[key] = [current_slots[key]] if current_slots.get(key) else []
                
                # 检查重复
                if isinstance(value, list):
                    for v in value:
                        if v not in current_slots[key]:
                            current_slots[key].append(v)
                            updated_count += 1
                elif value not in current_slots[key]:
                    current_slots[key].append(value)
                    updated_count += 1
            else:
                # Replace or LLM Judge (这里简化为 Replace，相信 Specialist 的判断)
                if current_slots.get(key) != value:
                    current_slots[key] = value
                    updated_count += 1
        
        if updated_count > 0:
            self._save_slots(user_id, current_slots)
            
        return {
            "success": True, 
            "updated_count": updated_count, 
            "errors": errors
        }
    
    def clear_profile(self, user_id: str) -> Dict:
        """清空用户画像"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM user_profile WHERE user_id = ?", (user_id,))
            conn.commit()
            logger.info(f"[Profile] 画像已清空 user_id={user_id}")
            return {"success": True}
        except Exception as e:
            logger.error(f"[Profile] 清空画像失败: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

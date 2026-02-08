"""M2-her 消息构建器 - 结构化格式"""

import os
from typing import List, Dict, Any
from .base_builder import BaseMessageBuilder, ChatContext


class M2HerMessageBuilder(BaseMessageBuilder):
    """M2-her 消息构建器 - 单 system + 历史对话格式"""

    def build_messages(self, context: ChatContext) -> List[Dict[str, str]]:
        messages = []

        # 1. 合并的 System 消息（固定指令 + MEMORY 块）
        system_content = self._build_system_content(context)
        messages.append({
            "role": "system",
            "content": system_content
        })

        # 2. 历史对话作为独立的 user/assistant 消息对
        if context.recent_history:
            for msg in context.recent_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        # 3. 当前用户输入
        messages.append({
            "role": "user",
            "content": context.user_query
        })

        return messages

    def _build_system_content(self, context: ChatContext) -> str:
        """构建合并的 system content"""
        parts = []

        # 第一部分：固定指令（身份、风格）
        identity_prompt = context.base_prompt
        if context.ai_name:
            identity_prompt = f"你的名字是【{context.ai_name}】。\n{identity_prompt}"
        identity_prompt += "\n\n【输出要求】直接输出回复内容，不要使用 Markdown 代码块。"
        parts.append(identity_prompt)

        # 第二部分：MEMORY 块
        memory_block = self._build_memory_block(context)
        parts.append(memory_block)

        return "\n\n" + "=" * 50 + "\n\n".join(parts)

    def _build_memory_block(self, context: ChatContext) -> str:
        """构建 MEMORY 块"""
        sections = ["===== MEMORY ====="]

        # 会话摘要
        if context.context_summary:
            sections.append(f"【会话摘要】\n{context.context_summary}")

        # 用户偏好/画像
        if context.profile_slots:
            profile_lines = [f"- {k}: {v}" for k, v in context.profile_slots.items()]
            sections.append(f"【用户偏好】\n" + "\n".join(profile_lines))

        # 已确认事实（过往记忆）
        if context.memory_block:
            sections.append(f"【已确认事实】\n{context.memory_block}")

        # 耳语建议（引导）
        if context.whisper_suggestion:
            sections.append(f"【引导建议】\n{context.whisper_suggestion}")

        # 当前时间
        if context.current_time_str:
            sections.append(f"【当前时间】\n{context.current_time_str}")

        sections.append("===== END =====")

        return "\n\n".join(sections)

    def get_model_params(self) -> Dict[str, Any]:
        return {
            "temperature": float(os.getenv("M2HER_TEMPERATURE", "1.0")),
            "top_p": float(os.getenv("M2HER_TOP_P", "0.95")),
            "max_tokens": int(os.getenv("M2HER_MAX_TOKENS", "2048")),
        }

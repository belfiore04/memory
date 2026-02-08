"""DeepSeek 消息构建器 - 保持现有的 XML 格式"""

from typing import List, Dict, Any
from .base_builder import BaseMessageBuilder, ChatContext


class DeepSeekMessageBuilder(BaseMessageBuilder):
    """DeepSeek 消息构建器 - 保持现有的 XML 一坨流格式"""

    def build_messages(self, context: ChatContext) -> List[Dict[str, str]]:
        # 拼装上下文块（复用现有逻辑）
        memory_block = ""
        if context.memory_block:
            memory_block = f"【过往记忆】\n{context.memory_block}\n"

        profile_block = ""
        if context.profile_slots:
            profile_block = "【用户资料】\n" + "\n".join(
                [f"- {k}: {v}" for k, v in context.profile_slots.items()]
            ) + "\n"

        context_summary = f"【长期聊史】{context.context_summary}\n" if context.context_summary else ""

        recent_history = ""
        if context.recent_history:
            recent_history = "【近期对话】\n" + "\n".join(
                [f"{h['role']}: {h['content']}" for h in context.recent_history]
            )

        whisper_block = ""
        if context.whisper_suggestion:
            whisper_block = f"\n<guidance>\n【耳语】{context.whisper_suggestion}\n</guidance>\n"

        base_prompt = context.base_prompt
        if context.ai_name:
            base_prompt = f"你的名字是【{context.ai_name}】。\n{base_prompt}"

        # 构建 XML 结构的 System Prompt
        final_system_prompt = f"""<role>
{base_prompt}
在此角色设定基础上，你必须严格按照特定格式输出：只输出回复内容字符串。
</role>


<context>
{memory_block}{profile_block}{context_summary}{recent_history}
</context>

<output_format>
严禁输出 Markdown 代码块标记（如 ```json），仅输出纯字符串。
</output_format>
{whisper_block}

<environment>
现在的时间是: {context.current_time_str}
</environment>

<task>
用户对你说：{context.user_query}
请根据上述要求生成回复：
</task>"""

        return [
            {"role": "system", "content": final_system_prompt},
            {"role": "user", "content": context.user_query}
        ]

    def get_model_params(self) -> Dict[str, Any]:
        return {
            "max_tokens": 2048,
        }

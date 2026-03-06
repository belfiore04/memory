"""
主 Agent：纯对话，无工具。适配为 async，支持多用户。
"""
import logging
from datetime import datetime
from pathlib import Path

from openai import AsyncOpenAI
from langfuse import observe, get_client as get_langfuse

from .config import (
    ROLEPLAY_CHAT_API_KEY,
    ROLEPLAY_CHAT_BASE_URL,
    ROLEPLAY_CHAT_MAX_TOKENS,
    ROLEPLAY_CHAT_MODEL,
    MAIN_INJECT_FILES,
    MAX_INJECT_CHARS,
)

logger = logging.getLogger(__name__)

# 复用单个 AsyncOpenAI client
_client = AsyncOpenAI(
    api_key=ROLEPLAY_CHAT_API_KEY,
    base_url=ROLEPLAY_CHAT_BASE_URL,
)


def _read_workspace_file(workspace_dir: Path, path: str) -> str:
    """读取 workspace 内的文件，不存在则返回空字符串。"""
    file_path = workspace_dir / path
    if file_path.exists():
        return file_path.read_text(encoding="utf-8")[:MAX_INJECT_CHARS]
    return ""


def build_system_prompt(workspace_dir: Path) -> str:
    """每轮对话前重新读取记忆文件，构建 system prompt。"""
    context_sections = []
    for mf in MAIN_INJECT_FILES:
        tag = mf["path"].replace(".md", "").lower()
        content = _read_workspace_file(workspace_dir, mf["path"]) or "（暂无内容）"
        context_sections.append(f"<{tag}>\n{content}\n</{tag}>")

    context_block = "\n\n".join(context_sections)

    return f"""<environment>
当前时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}
时区: Asia/Shanghai
</environment>

{context_block}"""


@observe(as_type="generation", name="Roleplay 主 Agent LLM 调用")
async def _call_llm(system_prompt: str, messages: list) -> str:
    """调用主 Agent 的 LLM，带 langfuse 追踪。"""
    get_langfuse().update_current_generation(
        model=ROLEPLAY_CHAT_MODEL,
        model_parameters={"max_tokens": ROLEPLAY_CHAT_MAX_TOKENS},
        input={"system": system_prompt, "messages": messages},
    )

    api_messages = [{"role": "system", "content": system_prompt}] + messages

    response = await _client.chat.completions.create(
        model=ROLEPLAY_CHAT_MODEL,
        max_tokens=ROLEPLAY_CHAT_MAX_TOKENS,
        messages=api_messages,
    )

    reply = response.choices[0].message.content or ""

    get_langfuse().update_current_generation(
        output=reply,
        usage_details={
            "input": response.usage.prompt_tokens,
            "output": response.usage.completion_tokens,
        },
    )

    return reply


@observe(name="Roleplay 角色对话")
async def chat(messages: list[dict], workspace_dir: Path) -> str:
    """
    发送一轮对话，返回文本回复。主 Agent 无工具，纯对话。

    Args:
        messages: 对话历史（不会被修改）
        workspace_dir: 用户 workspace 路径

    Returns:
        角色回复文本
    """
    system_prompt = build_system_prompt(workspace_dir)

    user_input = messages[-1]["content"] if messages else ""
    get_langfuse().update_current_trace(
        input=user_input,
    )

    reply = await _call_llm(system_prompt, messages)

    get_langfuse().update_current_trace(
        output=reply,
    )

    return reply

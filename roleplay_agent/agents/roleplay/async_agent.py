"""
异步 Agent：后台记忆管理，有文件工具。
保持同步 Anthropic client（在 BackgroundTasks 线程池中执行）。
"""
import logging
from datetime import datetime
from pathlib import Path

import anthropic
from langfuse import observe, get_client as get_langfuse

from .config import (
    ROLEPLAY_ASYNC_API_KEY,
    ROLEPLAY_ASYNC_BASE_URL,
    ROLEPLAY_ASYNC_MAX_TOKENS,
    ROLEPLAY_ASYNC_MODEL,
    ASYNC_INJECT_FILES,
    MAX_INJECT_CHARS,
)
from .tools import TOOL_SCHEMAS, get_tool_handlers

logger = logging.getLogger(__name__)

# 异步 Agent 独立的 Anthropic client
_client_kwargs = {"api_key": ROLEPLAY_ASYNC_API_KEY}
if ROLEPLAY_ASYNC_BASE_URL:
    _client_kwargs["base_url"] = ROLEPLAY_ASYNC_BASE_URL
_client = anthropic.Anthropic(**_client_kwargs)


def _read_workspace_file(workspace_dir: Path, path: str) -> str:
    file_path = workspace_dir / path
    if file_path.exists():
        return file_path.read_text(encoding="utf-8")[:MAX_INJECT_CHARS]
    return ""


def _build_async_system_prompt(workspace_dir: Path) -> str:
    """构建异步 Agent 的 system prompt。"""
    soul_content = _read_workspace_file(workspace_dir, "SOUL.md")

    # 判空逻辑
    clean_content = soul_content
    for header in ["# Soul", "## 性格", "## 说话风格", "## 当前状态"]:
        clean_content = clean_content.replace(header, "")
    soul_is_empty = not clean_content.strip()

    soul_init_block = ""
    if soul_is_empty:
        soul_init_block = """
### Soul 初始化（最高优先级）
SOUL.md 目前为空。你必须读取 CHARACTER.md，从中提取角色灵魂，写入 SOUL.md，格式：
# Soul
## 性格
（核心性格特质）
## 说话风格
（语气、用词、口头禅）
## 当前状态
（初始情绪和态度）
"""

    task_block = f"""## 你的任务
{soul_init_block}
你的可用工具和 workspace 文件权限详见 <tools> 中的 TOOLS.md。

### SOUL.md — 角色的活灵魂
记录角色的**行为模式、性格倾向、人格转折点**。
判断标准：如果删掉这条信息，角色的行为会变吗？会 → 留在 soul。不会 → 不属于这里。

允许记录的：
- 行为模式："面对调戏会耳根发红、找借口逃跑，但事后会默默关心"
- 性格倾向："会吃醋，酸溜溜地回应"
- 人格转折点："从被动害羞转变为主动承认感情"
- 关系状态变化："从陌生人升级为恋人"

不允许记录的：
- 具体对话复述："用户说XX，张山说YY"
- 场景细节："用户睡前问心跳快不快，张山说是"
- 事件流水账：逐条列出每次互动的细节

保持精简。三个维度（性格/说话风格/当前状态）加上重大转折点，总量控制在 30 行以内。
变化必须是渐进的、自然的，不要每轮都改。

### USER.md — 不能忘记的事实
存放关于用户的**持久事实**，这些是即使对话记忆被压缩也**绝不能丢失**的信息。

允许记录的：
- 身份信息：名字、性别、职业、年龄等
- 稳定喜好：喜欢吃什么、养什么宠物、兴趣爱好
- 重要承诺：约定、计划
- 关系里程碑：什么时候确定的关系（一句话）
- 性格特点：敏感、爱撒娇、占有欲强等（总结性的）

不允许记录的：
- 互动流水账："用户说XX，张山回应YY"
- 重复信息：同一个事实不要换不同说法反复记录
- 场景细节：某天某刻发生了什么具体对话

保持精简，控制在 30 行以内。

### MEMORY.md — 对话的压缩记忆
对最近的对话进行概括，保留关键情节和上下文。
用简洁的叙事体概括，不要逐条列出对话。
当 MEMORY.md 变长时，将旧内容进一步压缩概括，保持文件精简。
如果压缩过程中发现有不应丢失的细节（用户事实、重要承诺等），将其提取到 USER.md 后再压缩。"""

    # 注入记忆文件
    context_sections = []
    for mf in ASYNC_INJECT_FILES:
        tag = mf["path"].replace(".md", "").lower()
        content = _read_workspace_file(workspace_dir, mf["path"]) or "（暂无内容）"
        context_sections.append(f"<{tag}>\n{content}\n</{tag}>")

    context_block = "\n\n".join(context_sections)

    return f"""你是一个角色扮演系统的记忆管理助手。你的工作是在后台默默整理记忆文件。

{task_block}

<environment>
当前时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}
时区: Asia/Shanghai
</environment>

{context_block}"""


def _serialize_content(content) -> list[dict]:
    result = []
    for block in content:
        if block.type == "text":
            result.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            result.append({"type": "tool_use", "name": block.name, "input": block.input})
    return result


@observe(name="工具执行")
def _execute_tool(tool_name: str, tool_input: dict, tool_handlers: dict) -> str:
    get_langfuse().update_current_span(
        input={"tool": tool_name, "args": tool_input},
    )

    handler = tool_handlers.get(tool_name)
    if not handler:
        return f"错误: 未知工具 - {tool_name}"
    try:
        result = handler(tool_input)
    except PermissionError as e:
        result = str(e)
    except Exception as e:
        result = f"工具执行错误: {e}"

    get_langfuse().update_current_span(
        output=result,
    )
    return result


@observe(as_type="generation", name="异步 Agent LLM 调用")
def _call_llm(system_prompt: str, messages: list) -> anthropic.types.Message:
    get_langfuse().update_current_generation(
        model=ROLEPLAY_ASYNC_MODEL,
        model_parameters={"max_tokens": ROLEPLAY_ASYNC_MAX_TOKENS},
        input={"system": system_prompt, "messages": messages, "tools": TOOL_SCHEMAS},
    )

    response = _client.messages.create(
        model=ROLEPLAY_ASYNC_MODEL,
        max_tokens=ROLEPLAY_ASYNC_MAX_TOKENS,
        system=system_prompt,
        messages=messages,
        tools=TOOL_SCHEMAS,
    )

    get_langfuse().update_current_generation(
        output=_serialize_content(response.content),
        usage_details={
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
    )

    return response


@observe(name="异步 Agent")
def run_async_agent(conversation_messages: list[dict], workspace_dir: Path) -> None:
    """
    异步 Agent 主函数。接收最近的对话历史，自主决定读写哪些记忆文件。
    通过 tool use 循环执行，直到模型不再调用工具。
    """
    system_prompt = _build_async_system_prompt(workspace_dir)
    tool_handlers = get_tool_handlers(workspace_dir)

    get_langfuse().update_current_trace(
        name="异步记忆整理",
        input=f"对话轮数: {len(conversation_messages)}",
    )

    # 将对话历史格式化
    conversation_text = ""
    for msg in conversation_messages:
        role = "用户" if msg["role"] == "user" else "角色"
        conversation_text += f"【{role}】: {msg['content']}\n\n"

    messages = [
        {"role": "user", "content": f"以下是角色和用户的最近对话，请整理记忆：\n\n{conversation_text}"}
    ]

    while True:
        response = _call_llm(system_prompt, messages)

        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        tool_uses = [b for b in assistant_content if b.type == "tool_use"]
        if not tool_uses:
            break

        tool_results = []
        for tool_use in tool_uses:
            result = _execute_tool(tool_use.name, tool_use.input, tool_handlers)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})

    get_langfuse().update_current_trace(
        output="记忆整理完成",
    )
    logger.info(f"Async agent completed for workspace: {workspace_dir}")

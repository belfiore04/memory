"""
角色扮演服务模块
封装 roleplay package 的调用，实现与文件记忆系统的集成。
"""
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from roleplay_agent.agents.roleplay.config import MAX_HISTORY_TURNS, ROLEPLAY_WORKSPACES_DIR
from roleplay_agent.agents.roleplay.workspace import (
    get_workspace_dir,
    init_workspace_with_content,
    list_workspace_files,
    read_workspace_file,
    reset_workspace,
    workspace_exists,
)
from roleplay_agent.agents.roleplay.chat_agent import chat
from roleplay_agent.agents.roleplay.async_agent import run_async_agent

logger = logging.getLogger(__name__)


class RoleplayService:
    """
    角色扮演服务

    每个用户有独立的 workspace，包含：
    - CHARACTER.md: 角色设定（从角色库复制，只读）
    - SOUL.md: 角色灵魂（由 AI 生成和维护）
    - USER.md: 用户画像（由 AI 维护）
    - MEMORY.md: 对话记忆
    - NOTES.md: 角色私密笔记
    - TOOLS.md: 工具目录（只读）
    """

    def __init__(self):
        ROLEPLAY_WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Roleplay workspaces directory: {ROLEPLAY_WORKSPACES_DIR}")

    async def chat_interact(
        self,
        user_id: str,
        message: str,
        history: List[Dict[str, str]],
    ) -> Dict:
        """
        主对话接口。

        Args:
            user_id: 用户 ID
            message: 用户输入消息
            history: 最近的对话历史

        Returns:
            {"reply": str, "workspace_dir": Path, "messages": list}
        """
        workspace_dir = get_workspace_dir(user_id)
        if not workspace_exists(user_id):
            raise RuntimeError("请先选择角色")

        # 构建消息列表
        messages = list(history)
        messages.append({"role": "user", "content": message})

        # 截断历史
        max_messages = MAX_HISTORY_TURNS * 2
        if len(messages) > max_messages:
            messages = messages[-max_messages:]

        # 调用主 Agent（async）
        start = time.time()
        reply = await chat(messages, workspace_dir)
        latency_ms = int((time.time() - start) * 1000)

        # 追加 assistant 消息到历史
        messages.append({"role": "assistant", "content": reply})

        return {
            "reply": reply,
            "workspace_dir": workspace_dir,
            "messages": messages,
            "latency_ms": latency_ms,
        }

    def run_async_memory_agent(
        self,
        conversation_messages: List[Dict[str, str]],
        workspace_dir: Path,
    ) -> None:
        """在后台线程中运行异步 Agent 整理记忆。"""
        try:
            run_async_agent(conversation_messages, workspace_dir)
        except Exception as e:
            logger.error(f"Async agent error: {e}")

    def init_character(self, user_id: str, content: str) -> Path:
        """初始化用户角色 workspace。"""
        return init_workspace_with_content(user_id, content)


    def get_workspace_files(self, user_id: str) -> List[Dict]:
        return list_workspace_files(user_id)

    def get_file_content(self, user_id: str, filename: str) -> Optional[str]:
        return read_workspace_file(user_id, filename)

    def get_notes(self, user_id: str) -> str:
        content = read_workspace_file(user_id, "NOTES.md")
        return content or ""

    def reset(self, user_id: str) -> None:
        reset_workspace(user_id)

    def has_workspace(self, user_id: str) -> bool:
        return workspace_exists(user_id)


# 全局服务实例（单例）
_roleplay_service: Optional[RoleplayService] = None


def get_roleplay_service() -> RoleplayService:
    global _roleplay_service
    if _roleplay_service is None:
        _roleplay_service = RoleplayService()
    return _roleplay_service

import os
from pathlib import Path

# 主 Agent API（纯对话，无工具，OpenAI 兼容）
ROLEPLAY_CHAT_API_KEY = os.getenv("ROLEPLAY_CHAT_API_KEY", os.getenv("CHAT_API_KEY", ""))
ROLEPLAY_CHAT_BASE_URL = os.getenv("ROLEPLAY_CHAT_BASE_URL", os.getenv("CHAT_BASE_URL", ""))
ROLEPLAY_CHAT_MODEL = os.getenv("ROLEPLAY_CHAT_MODEL", os.getenv("CHAT_MODEL", "deepseek-v3.2"))
ROLEPLAY_CHAT_MAX_TOKENS = int(os.getenv("ROLEPLAY_CHAT_MAX_TOKENS", "4096"))

# 异步 Agent API（后台记忆管理，有文件工具，Anthropic 兼容）
ROLEPLAY_ASYNC_API_KEY = os.getenv("ROLEPLAY_ASYNC_API_KEY", os.getenv("ASYNC_AGENT_API_KEY", os.getenv("MINIMAX_API_KEY", "")))
ROLEPLAY_ASYNC_BASE_URL = os.getenv("ROLEPLAY_ASYNC_BASE_URL", os.getenv("ASYNC_AGENT_BASE_URL", "https://api.minimaxi.com/anthropic"))
ROLEPLAY_ASYNC_MODEL = os.getenv("ROLEPLAY_ASYNC_MODEL", os.getenv("ASYNC_AGENT_MODEL", "MiniMax-M2.5"))
ROLEPLAY_ASYNC_MAX_TOKENS = int(os.getenv("ROLEPLAY_ASYNC_MAX_TOKENS", "4096"))

# roleplay_agent 根目录
_PKG_ROOT = Path(__file__).parent.parent.parent

# Workspace 基础目录
ROLEPLAY_WORKSPACES_DIR = Path(os.getenv(
    "ROLEPLAY_WORKSPACES_DIR",
    str(_PKG_ROOT / "roleplay_workspaces")
))

# 主 Agent 注入的文件
MAIN_INJECT_FILES = [
    {"path": "CHARACTER.md", "label": "角色设定"},
    {"path": "SOUL.md", "label": "角色灵魂"},
    {"path": "USER.md", "label": "用户信息"},
    {"path": "MEMORY.md", "label": "对话记忆"},
]

# 异步 Agent 注入的文件
ASYNC_INJECT_FILES = [
    {"path": "CHARACTER.md", "label": "角色设定"},
    {"path": "SOUL.md", "label": "角色灵魂"},
    {"path": "USER.md", "label": "用户信息"},
    {"path": "MEMORY.md", "label": "对话记忆"},
    {"path": "TOOLS.md", "label": "工具目录"},
]

# 每个记忆文件注入的最大字符数
MAX_INJECT_CHARS = int(os.getenv("MAX_INJECT_CHARS", "10000"))

# 对话历史保留轮数
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "50"))

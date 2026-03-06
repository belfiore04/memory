"""
每用户 workspace 管理：创建、读写、路径安全。
"""
import logging
import shutil
import threading
from pathlib import Path
from typing import Dict, List, Optional

from .config import ROLEPLAY_WORKSPACES_DIR

logger = logging.getLogger(__name__)

# Per-user locks for concurrent write safety
_user_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


def _get_user_lock(user_id: str) -> threading.Lock:
    with _locks_lock:
        if user_id not in _user_locks:
            _user_locks[user_id] = threading.Lock()
        return _user_locks[user_id]


# 默认模板（首次创建 workspace 时使用）
TEMPLATES = {
    "USER.md": """# USER.md - About Your Human

_Learn about the person you're helping. Update this as you go._

- **Name:**
- **What to call them:**
- **Timezone:**
- **Notes:**

## Context

_(What do they care about? What projects are they working on? What annoys them? What makes them laugh? Build this over time.)_


## 喜好

## 习惯
---

The more you know, the better you can help. But remember — you're learning about a person, not building a dossier. Respect the difference.
""",
    "SOUL.md": """# Soul

## 性格

## 说话风格

## 当前状态
""",
    "MEMORY.md": "# 对话记忆",
    "NOTES.md": "",
    "TOOLS.md": """# 可用工具

## read_file
读取 workspace 内的文件。修改任何文件前，先用这个查看当前内容。

## write_file
创建或覆盖文件。适合大面积重写。

## edit_file
精确替换文件中的一段文本。适合小范围修改，无需重写整个文件。

## append_note
以角色的口吻写一条私人笔记。用户可以查看，但不会出现在你的上下文中。
适合写笔记的时机：角色内心有触动、对用户产生了新的感受、发生了值得角色私下记录的事。
不必每轮都写。平淡的日常对话不需要笔记，只在角色真的有话想说时才写。

# Workspace 文件目录

| 文件 | 读 | 写 | 编辑 | 说明 |
|---|---|---|---|---|
| CHARACTER.md | ✓ | ✗ | ✗ | 角色设定，只读 |
| SOUL.md | ✓ | ✓ | ✓ | 角色的活灵魂，随对话自然演变 |
| USER.md | ✓ | ✓ | ✓ | 关于用户的持久事实 |
| MEMORY.md | ✓ | ✓ | ✓ | 对话的压缩记忆 |
| NOTES.md | ✗ | ✗ | ✗ | 只能通过 append_note 工具追加 |
""",
}


def get_workspace_dir(user_id: str) -> Path:
    """返回用户的 workspace 路径。"""
    return ROLEPLAY_WORKSPACES_DIR / user_id


def init_workspace_with_content(user_id: str, content: str) -> Path:
    """
    通过用户提供的内容初始化 workspace。
    """
    workspace = get_workspace_dir(user_id)
    workspace.mkdir(parents=True, exist_ok=True)

    # 写入 CHARACTER.md
    char_dest = workspace / "CHARACTER.md"
    char_dest.write_text(content, encoding="utf-8")
    logger.info(f"Created CHARACTER.md for user {user_id} with custom content")

    # 创建模板文件（仅不存在时）
    for filename, template in TEMPLATES.items():
        file_path = workspace / filename
        if not file_path.exists():
            file_path.write_text(template, encoding="utf-8")
            logger.info(f"Created {filename} for user {user_id}")

    return workspace


def reset_workspace(user_id: str) -> None:
    """重置用户 workspace 的记忆文件（保留 CHARACTER.md）。"""
    workspace = get_workspace_dir(user_id)
    if not workspace.exists():
        return

    with _get_user_lock(user_id):
        for filename, template in TEMPLATES.items():
            (workspace / filename).write_text(template, encoding="utf-8")

    logger.info(f"Reset workspace for user {user_id}")


def read_workspace_file(user_id: str, filename: str) -> Optional[str]:
    """读取 workspace 中的文件内容。"""
    workspace = get_workspace_dir(user_id)
    file_path = _safe_resolve(workspace, filename)
    if file_path.exists():
        return file_path.read_text(encoding="utf-8")
    return None


def list_workspace_files(user_id: str) -> List[Dict]:
    """列出 workspace 文件状态。"""
    workspace = get_workspace_dir(user_id)
    files = []
    for filename in ["CHARACTER.md", "SOUL.md", "USER.md", "MEMORY.md", "NOTES.md"]:
        file_path = workspace / filename
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            files.append({
                "filename": filename,
                "size": file_path.stat().st_size,
                "lines": len(content.splitlines()),
                "exists": True,
            })
        else:
            files.append({"filename": filename, "size": 0, "lines": 0, "exists": False})
    return files


def workspace_exists(user_id: str) -> bool:
    """检查用户 workspace 是否已初始化。"""
    workspace = get_workspace_dir(user_id)
    return (workspace / "CHARACTER.md").exists()


def _safe_resolve(workspace_dir: Path, path: str) -> Path:
    """将相对路径解析为 workspace 内的绝对路径，防止路径逃逸。"""
    resolved = (workspace_dir / path).resolve()
    workspace_resolved = workspace_dir.resolve()
    if not str(resolved).startswith(str(workspace_resolved)):
        raise PermissionError(f"禁止访问 workspace 之外的路径: {path}")
    return resolved

"""
异步 Agent 的工具：文件读写 + 笔记追加。
所有函数接受 workspace_dir 参数，支持多用户隔离。
"""
from datetime import datetime
from pathlib import Path


PROTECTED_FILES = {"CHARACTER.md", "TOOLS.md"}


def _safe_resolve(workspace_dir: Path, path: str) -> Path:
    """将相对路径解析为 workspace 内的绝对路径，防止路径逃逸。"""
    resolved = (workspace_dir / path).resolve()
    workspace_resolved = workspace_dir.resolve()
    if not str(resolved).startswith(str(workspace_resolved)):
        raise PermissionError(f"禁止访问 workspace 之外的路径: {path}")
    return resolved


def read_file(workspace_dir: Path, path: str) -> str:
    file_path = _safe_resolve(workspace_dir, path)
    if not file_path.exists():
        return f"错误: 文件不存在 - {path}"
    return file_path.read_text(encoding="utf-8")


def write_file(workspace_dir: Path, path: str, content: str) -> str:
    if Path(path).name in PROTECTED_FILES:
        return f"错误: {path} 是只读文件，不允许修改"
    file_path = _safe_resolve(workspace_dir, path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return f"已写入: {path}"


def edit_file(workspace_dir: Path, path: str, old_text: str, new_text: str) -> str:
    if Path(path).name in PROTECTED_FILES:
        return f"错误: {path} 是只读文件，不允许修改"
    file_path = _safe_resolve(workspace_dir, path)
    if not file_path.exists():
        return f"错误: 文件不存在 - {path}"
    content = file_path.read_text(encoding="utf-8")
    if old_text not in content:
        return f"错误: 未找到要替换的文本"
    count = content.count(old_text)
    if count > 1:
        return f"错误: 找到 {count} 处匹配，请提供更精确的文本以确保唯一匹配"
    new_content = content.replace(old_text, new_text, 1)
    file_path.write_text(new_content, encoding="utf-8")
    return f"已更新: {path}"


def append_note(workspace_dir: Path, content: str) -> str:
    file_path = workspace_dir / "NOTES.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n---\n{timestamp}\n\n{content}\n"
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(entry)
    return f"已追加笔记 ({timestamp})"


def get_tool_handlers(workspace_dir: Path) -> dict:
    """工厂函数：返回绑定了 workspace_dir 的工具处理器。"""
    return {
        "read_file": lambda args: read_file(workspace_dir, args["path"]),
        "write_file": lambda args: write_file(workspace_dir, args["path"], args["content"]),
        "edit_file": lambda args: edit_file(workspace_dir, args["path"], args["old_text"], args["new_text"]),
        "append_note": lambda args: append_note(workspace_dir, args["content"]),
    }


# Tool schemas（不依赖 workspace，全局通用）
TOOL_SCHEMAS = [
    {
        "name": "read_file",
        "description": "读取 workspace 内的文件内容。用于查看你的记忆文件或其他文件。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件的相对路径，如 'USER.md'、'CHARACTER.md'、'SOUL.md'、'MEMORY.md'",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "创建或覆盖 workspace 内的文件。用于更新你的记忆、记录新的信息。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件的相对路径"},
                "content": {"type": "string", "description": "要写入的完整文件内容"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "精确替换文件中的一段文本。适合小范围修改，无需重写整个文件。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件的相对路径"},
                "old_text": {"type": "string", "description": "要被替换的原始文本（必须精确匹配）"},
                "new_text": {"type": "string", "description": "替换后的新文本"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "append_note",
        "description": "以角色的口吻写一条私人笔记。内容是角色的内心独白、对用户的看法、当天的感受等。用户可以查看这些笔记，但笔记不会出现在你的上下文中。当你觉得角色此刻有话想说、有情绪想记录、或对用户产生了新的感受时，写一条。不必每轮都写，没什么想说的时候就不写。",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "笔记内容，用角色自己的语气和视角书写",
                }
            },
            "required": ["content"],
        },
    },
]

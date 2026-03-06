"""消息构建器抽象基类"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ChatContext:
    """聊天上下文数据对象"""
    user_query: str
    base_prompt: str
    ai_name: Optional[str] = None
    memory_block: str = ""
    profile_slots: Dict[str, Any] = field(default_factory=dict)
    context_summary: str = ""
    recent_history: List[Dict[str, str]] = field(default_factory=list)
    whisper_suggestion: Optional[str] = None
    current_time_str: str = ""


class BaseMessageBuilder(ABC):
    """消息构建器抽象基类"""

    @abstractmethod
    def build_messages(self, context: ChatContext) -> List[Dict[str, str]]:
        """
        构建发送给 LLM 的消息列表

        Args:
            context: 聊天上下文数据

        Returns:
            List[Dict]: [{"role": "...", "content": "..."}, ...]
        """
        pass

    @abstractmethod
    def get_model_params(self) -> Dict[str, Any]:
        """
        获取模型特定参数

        Returns:
            Dict: {"temperature": ..., "max_tokens": ..., ...}
        """
        pass

"""工厂函数：获取 Builder、Client、Model 名"""

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langfuse.openai import AsyncOpenAI
    from .base_builder import BaseMessageBuilder

# 单例缓存
_llm_clients = {}
_builders = {}


def get_chat_provider() -> str:
    """获取当前使用的 Chat Provider"""
    return os.getenv("CHAT_PROVIDER", "deepseek").lower()


def get_message_builder() -> "BaseMessageBuilder":
    """获取消息构建器（单例）"""
    from .deepseek_builder import DeepSeekMessageBuilder
    from .m2her_builder import M2HerMessageBuilder

    provider = get_chat_provider()

    if provider not in _builders:
        if provider == "m2her":
            _builders[provider] = M2HerMessageBuilder()
        else:
            _builders[provider] = DeepSeekMessageBuilder()

    return _builders[provider]


def get_chat_llm_client() -> "AsyncOpenAI":
    """获取 LLM 客户端（单例）"""
    from langfuse.openai import AsyncOpenAI

    provider = get_chat_provider()

    if provider not in _llm_clients:
        if provider == "m2her":
            _llm_clients[provider] = AsyncOpenAI(
                api_key=os.getenv("M2HER_API_KEY") or os.getenv("MINIMAX_API_KEY"),
                base_url=os.getenv("M2HER_BASE_URL", "https://api.minimaxi.com/v1"),
            )
        else:
            _llm_clients[provider] = AsyncOpenAI(
                api_key=os.getenv("CHAT_API_KEY"),
                base_url=os.getenv("CHAT_BASE_URL"),
            )

    return _llm_clients[provider]


def get_chat_model_name() -> str:
    """获取模型名称"""
    provider = get_chat_provider()
    if provider == "m2her":
        return os.getenv("M2HER_MODEL", "M2-her")
    return os.getenv("CHAT_MODEL", "deepseek-v3")

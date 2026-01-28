#!/usr/bin/env python3
"""
LLM 调用日志工具
提供统一的 LLM 调用日志记录，包括输入、输出、耗时和 Token 统计
"""

import os
import json
import time
import logging
import functools
from typing import Any, Callable, Optional
from datetime import datetime

# 配置日志
logger = logging.getLogger("llm_logger")

# 是否启用详细日志（环境变量控制）
VERBOSE_LLM_LOGGING = os.getenv("VERBOSE_LLM_LOGGING", "true").lower() == "true"

# 日志文件路径
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LLM_LOG_FILE = os.path.join(LOG_DIR, "llm_calls.jsonl")

def ensure_log_dir():
    """确保日志目录存在"""
    os.makedirs(LOG_DIR, exist_ok=True)

def log_llm_call(
    caller: str,
    model: str,
    messages: list,
    response_text: str,
    duration_ms: float,
    usage: Optional[dict] = None,
    error: Optional[str] = None
):
    """
    记录一次 LLM 调用
    
    Args:
        caller: 调用方标识 (e.g., "ExtractionAgent", "MemoryService._should_store")
        model: 模型名称
        messages: 输入消息列表
        response_text: LLM 返回的文本
        duration_ms: 调用耗时（毫秒）
        usage: Token 使用统计 (可选)
        error: 错误信息 (可选)
    """
    ensure_log_dir()
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "caller": caller,
        "model": model,
        "duration_ms": round(duration_ms, 2),
        "input_messages": messages if VERBOSE_LLM_LOGGING else f"[{len(messages)} messages]",
        "output": response_text[:500] if VERBOSE_LLM_LOGGING else f"[{len(response_text)} chars]",
        "usage": usage,
        "error": error
    }
    
    # 控制台日志
    status = "✅" if not error else "❌"
    token_info = ""
    if usage:
        token_info = f" | Tokens: {usage.get('total_tokens', 'N/A')}"
    
    logger.info(f"{status} [{caller}] {model} | {duration_ms:.0f}ms{token_info}")
    
    if VERBOSE_LLM_LOGGING:
        # 简短显示输入输出
        input_preview = str(messages[-1].get("content", ""))[:100] if messages else ""
        output_preview = response_text[:100] if response_text else ""
        logger.debug(f"  ↳ Input: {input_preview}...")
        logger.debug(f"  ↳ Output: {output_preview}...")
    
    # 写入 JSONL 文件
    try:
        with open(LLM_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"Failed to write LLM log: {e}")


def llm_logged(caller_name: str):
    """
    装饰器：自动记录 LLM 调用
    
    用法:
        @llm_logged("ExtractionAgent.analyze_query")
        def some_method(self, ...):
            ...
    
    注意：被装饰的函数应返回 (response_text, usage) 或 OpenAI ChatCompletion 对象
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            error = None
            response_text = ""
            usage = None
            
            try:
                result = func(*args, **kwargs)
                
                # 尝试提取 response_text 和 usage
                if hasattr(result, 'choices'):
                    # OpenAI ChatCompletion object
                    response_text = result.choices[0].message.content if result.choices else ""
                    usage = result.usage.model_dump() if hasattr(result, 'usage') and result.usage else None
                elif isinstance(result, tuple) and len(result) == 2:
                    response_text, usage = result
                elif isinstance(result, str):
                    response_text = result
                else:
                    response_text = str(result)
                
                return result
                
            except Exception as e:
                error = str(e)
                raise
            
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                # 尝试提取 model 和 messages
                model = "unknown"
                messages = []
                
                # 从 kwargs 或 args 中尝试提取
                if 'model' in kwargs:
                    model = kwargs['model']
                if 'messages' in kwargs:
                    messages = kwargs['messages']
                
                log_llm_call(
                    caller=caller_name,
                    model=model,
                    messages=messages,
                    response_text=response_text,
                    duration_ms=duration_ms,
                    usage=usage,
                    error=error
                )
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            error = None
            response_text = ""
            usage = None
            
            try:
                result = await func(*args, **kwargs)
                
                if hasattr(result, 'choices'):
                    response_text = result.choices[0].message.content if result.choices else ""
                    usage = result.usage.model_dump() if hasattr(result, 'usage') and result.usage else None
                elif isinstance(result, tuple) and len(result) == 2:
                    response_text, usage = result
                elif isinstance(result, str):
                    response_text = result
                else:
                    response_text = str(result)
                
                return result
                
            except Exception as e:
                error = str(e)
                raise
            
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                model = kwargs.get('model', 'unknown')
                messages = kwargs.get('messages', [])
                
                log_llm_call(
                    caller=caller_name,
                    model=model,
                    messages=messages,
                    response_text=response_text,
                    duration_ms=duration_ms,
                    usage=usage,
                    error=error
                )
        
        # 检查是否是异步函数
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    
    return decorator


# 配置 Graphiti 的日志级别
def configure_graphiti_logging(level: int = logging.INFO):
    """
    配置 Graphiti 库的日志级别以捕获其内部 LLM 调用
    """
    # Graphiti 使用的 logger 名称
    graphiti_loggers = [
        "graphiti_core",
        "graphiti_core.graphiti",
        "graphiti_core.llm_client",
    ]
    
    for logger_name in graphiti_loggers:
        lib_logger = logging.getLogger(logger_name)
        lib_logger.setLevel(level)
        
        # 添加 handler 如果没有的话
        if not lib_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            lib_logger.addHandler(handler)
    
    logger.info(f"Graphiti logging configured at level {logging.getLevelName(level)}")


if __name__ == "__main__":
    # 测试日志功能
    logging.basicConfig(level=logging.DEBUG)
    
    log_llm_call(
        caller="TestCaller",
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}],
        response_text="Hi there! How can I help you?",
        duration_ms=150.5,
        usage={"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18}
    )
    
    print(f"Log written to: {LLM_LOG_FILE}")

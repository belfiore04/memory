#!/usr/bin/env python3
"""测试 LLM Builder"""

import sys
import os

# 确保可以直接导入 llm 子模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 绕过 services/__init__.py，直接导入 llm 模块
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# 加载模块
base_builder = load_module("base_builder", "services/llm/base_builder.py")
deepseek_builder = load_module("deepseek_builder", "services/llm/deepseek_builder.py")
m2her_builder = load_module("m2her_builder", "services/llm/m2her_builder.py")

ChatContext = base_builder.ChatContext
DeepSeekMessageBuilder = deepseek_builder.DeepSeekMessageBuilder
M2HerMessageBuilder = m2her_builder.M2HerMessageBuilder

# 测试数据
ctx = ChatContext(
    user_query='你好',
    base_prompt='你是一个塔罗师',
    ai_name='小塔',
    memory_block='用户喜欢占卜',
    profile_slots={'nickname': '小明'},
    context_summary='用户之前问过工作运势',
    recent_history=[
        {'role': 'user', 'content': '帮我看看'},
        {'role': 'assistant', 'content': '好的，请抽一张牌'}
    ],
    whisper_suggestion=None,
    current_time_str='2026-02-05 14:30 (下午)'
)

# 测试 DeepSeek Builder
print('=== DeepSeek Messages ===')
ds = DeepSeekMessageBuilder()
msgs = ds.build_messages(ctx)
print(f'消息数量: {len(msgs)}')
for i, m in enumerate(msgs):
    content_preview = m['content'][:100].replace('\n', '\\n')
    print(f'[{i}] role={m["role"]}')
    print(f'    content[:100]={content_preview}...')
print(f'参数: {ds.get_model_params()}')

print()

# 测试 M2-her Builder
print('=== M2-her Messages ===')
m2 = M2HerMessageBuilder()
msgs = m2.build_messages(ctx)
print(f'消息数量: {len(msgs)}')
for i, m in enumerate(msgs):
    content_preview = m['content'][:100].replace('\n', '\\n')
    print(f'[{i}] role={m["role"]}')
    print(f'    content[:100]={content_preview}...')
print(f'参数: {m2.get_model_params()}')

print()
print('=== 测试通过 ===')

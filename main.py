import openai
from langfuse.openai import OpenAI as LangfuseOpenAI
from langfuse.openai import AsyncOpenAI as LangfuseAsyncOpenAI
import os
import logging
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# [Langfuse] 全局 Monkey Patch
# 必须在导入任何使用 openai 的模块之前执行
# 这将确保 Graphiti 内部实例化的 OpenAI 客户端自动拥有追踪能力
openai.OpenAI = LangfuseOpenAI
openai.AsyncOpenAI = LangfuseAsyncOpenAI

# [Graphiti] 兼容性 Monkey Patch
# 用于修复 DashScope API 的限制：
# 1. 强制在 JSON 模式下 System Prompt 包含 "JSON"
# 2. 限制 max_tokens <= 4096 (避免 8192 限制错误)
import graphiti_core.llm_client.openai_generic_client as graphiti_client
from typing import Any, List
import json
from openai.types.chat import ChatCompletionMessageParam

original_generate = graphiti_client.OpenAIGenericClient._generate_response

async def patched_generate_response(
    self,
    messages: List[Any],
    response_model=None,
    max_tokens=None,
    model_size=None
):
    # 1. 修正 max_tokens
    safe_max_tokens = 4000
    if isinstance(max_tokens, int) and max_tokens > 4096:
        safe_max_tokens = 4096
    
    # 2. 修正 Messages 
    # (a) System Prompt 必须包含 "json"
    # (b) 如果有 response_model，将 Schema 注入 Prompt
    openai_messages: List[ChatCompletionMessageParam] = []
    has_json_instruction = False
    
    schema_instruction = ""
    if response_model:
        try:
            # 获取 Pydantic schema 并简化
            schema = response_model.model_json_schema()
            schema_json = json.dumps(schema, ensure_ascii=False)
            schema_instruction = f"\n\nOutput strictly in JSON format matching this schema:\n{schema_json}"
        except Exception:
            pass

    for m in messages:
        # 清理内容
        content = self._clean_input(m.content)
        if m.role == 'system':
            if "json" in content.lower():
                has_json_instruction = True
            # 注入 Schema 到 system prompt
            if schema_instruction:
                content += schema_instruction
                # 只注入一次
                schema_instruction = "" 
            openai_messages.append({'role': 'system', 'content': content})
        elif m.role == 'user':
            openai_messages.append({'role': 'user', 'content': content})
    
    # 如果没有 JSON 提示，强制追加
    if not has_json_instruction and openai_messages:
        # 找到第一个 system message 追加
        for msg in openai_messages:
            if msg['role'] == 'system':
                msg['content'] += " Ensure output is valid JSON."
                has_json_instruction = True
                break
        # 如果还没找到 (比如没有 system message)，新增一个
        if not has_json_instruction:
             openai_messages.insert(0, {'role': 'system', 'content': "You are a helpful assistant. Ensure output is valid JSON."})

    # 3. 构造 response format
    # DashScope 只支持 type: json_object
    response_format = {"type": "json_object"}
    
    # 4. 调用原生 API
    try:
        response = await self.client.chat.completions.create(
            model=self.model or graphiti_client.DEFAULT_MODEL,
            messages=openai_messages,
            temperature=self.temperature,
            max_tokens=safe_max_tokens,
            response_format=response_format,
        )
        result_text = response.choices[0].message.content or '{}'
        
        # 简单清理 markdown
        if result_text.strip().startswith("```"):
             result_text = result_text.split("```")[1]
             if result_text.strip().startswith("json"):
                 result_text = result_text.strip()[4:]
        
        result_json = json.loads(result_text)
        
        # 5. 结果适配 (Wrapper fix & Correction)
        # 根据 response_model 进行特定修复
        model_name = getattr(response_model, "__name__", "")
        
        # Case A: ExtractedEntities
        if response_model and model_name == "ExtractedEntities":
            # 期望: {"extracted_entities": [...]}
            if isinstance(result_json, list):
                result_json = {"extracted_entities": result_json}
            elif isinstance(result_json, dict):
                if "extracted_entities" not in result_json:
                    found_list = None
                    for k, v in result_json.items():
                        if isinstance(v, list):
                            found_list = v
                            break
                    if found_list is not None:
                         result_json = {"extracted_entities": found_list}
                    else:
                        result_json = {"extracted_entities": []}

        # Case B: NodeResolutions (Dedupe)
        # 修复 duplicates 字段应该是 list[int] 但返回了 int 的情况
        if response_model and model_name == "NodeResolutions":
            # 期望: {"entity_resolutions": [...]}
            resolutions = []
            if isinstance(result_json, dict):
                resolutions = result_json.get("entity_resolutions", [])
            elif isinstance(result_json, list):
                # 假如直接返回了列表，尝试包装
                resolutions = result_json
                result_json = {"entity_resolutions": resolutions}
            
            # 遍历修复每个 item
            if isinstance(resolutions, list):
                for item in resolutions:
                    if isinstance(item, dict):
                         # 修复 duplicates 类型
                         dups = item.get("duplicates")
                         if isinstance(dups, int):
                             item["duplicates"] = [dups]
                         elif isinstance(dups, str):
                             # 修复字符串类型，如 '[0]' 或 '[]'
                             try:
                                 parsed = json.loads(dups)
                                 if isinstance(parsed, list):
                                     item["duplicates"] = parsed
                                 elif isinstance(parsed, int):
                                     item["duplicates"] = [parsed]
                                 else:
                                     item["duplicates"] = []
                             except:
                                 item["duplicates"] = []
                         elif dups is None:
                             item["duplicates"] = []
                         
                         # 确保 duplicate_idx 存在且类型正确
                         dup_idx = item.get("duplicate_idx")
                         if dup_idx is None:
                             item["duplicate_idx"] = -1
                         elif isinstance(dup_idx, str):
                             try:
                                 item["duplicate_idx"] = int(dup_idx)
                             except:
                                 item["duplicate_idx"] = -1

        return result_json

    except Exception as e:
        logging.getLogger(__name__).error(f"[Graphiti Patch] Error: {e}")
        raise

# 应用补丁
graphiti_client.OpenAIGenericClient._generate_response = patched_generate_response

from fastapi import FastAPI
from routers import memory, context, profile, chat, auth
from routers import psychology

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/server.log")
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Memory API (Modular)",
    description="智能记忆管理 API - 模块化架构",
    version="3.0.0"
)

from fastapi.middleware.cors import CORSMiddleware

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境建议指定具体域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法 (GET, POST, OPTIONS 等)
    allow_headers=["*"],  # 允许所有请求头
)

# 注册路由
app.include_router(memory.router)
app.include_router(context.router)
app.include_router(profile.router)
app.include_router(chat.router)
app.include_router(psychology.router)
app.include_router(auth.router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "memory-api", "version": "3.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

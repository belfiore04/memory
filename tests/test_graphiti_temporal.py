import asyncio
import os
import sys
from datetime import datetime, timezone

# Ensure we can import graphiti_core
# Depending on installation, it might be in site-packages
from graphiti_core import Graphiti
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.nodes import EpisodeType

# DashScope 配置 (Hardcoded for testing based on .env content provided earlier)
DASHSCOPE_API_KEY = "sk-8fda6213e6b740e299e093c615f98633"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

async def main():
    print(f"Connecting to FalkorDB on localhost:6380...")
    
    # LLM 配置 (使用 qwen-plus)
    # Graphiti 需要 structured output，qwen-plus 支持较好
    llm_config = LLMConfig(
        api_key=DASHSCOPE_API_KEY,
        model="qwen-plus",
        small_model="qwen-turbo",
        base_url=DASHSCOPE_BASE_URL,
    )
    llm_client = OpenAIGenericClient(config=llm_config)

    # Embedding 配置 (使用 text-embedding-v4)
    # Dimension 1024 is standard for text-embedding-v3/v4 small variants usually, verifying v4 dims
    # text-embedding-v4 dimensions can be 1536 or 1024 or 768 depending on params, default is often larger.
    # We will assume 1024 based on plan.
    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=DASHSCOPE_API_KEY,
            embedding_model="text-embedding-v4",
            embedding_dim=1024,
            base_url=DASHSCOPE_BASE_URL,
        )
    )

    # 初始化 Graphiti，注意端口是 6380
    driver = FalkorDriver(host="localhost", port=6380)
    
    graphiti = Graphiti(
        graph_driver=driver,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=OpenAIRerankerClient(client=llm_client, config=llm_config),
    )
    
    try:
        print("Adding first preference (Apple) at 2026-01-20...")
        # 添加记忆（带时间戳）
        await graphiti.add_episode(
            name="user_preference_1",
            episode_body="用户喜欢吃苹果",
            source=EpisodeType.text,
            source_description="user chat input",
            reference_time=datetime(2026, 1, 20, tzinfo=timezone.utc),
        )
        
        print("Adding preference update (Orange) at 2026-01-22...")
        # 添加更新后的偏好
        await graphiti.add_episode(
            name="user_preference_2", 
            episode_body="用户不再喜欢苹果了，用户现在只喜欢吃橙子",
            source=EpisodeType.text,
            source_description="user chat input",
            reference_time=datetime(2026, 1, 22, tzinfo=timezone.utc),
        )
        
        print("Searching for '用户喜欢吃什么水果'...")
        # 搜索并检查时序字段
        results = await graphiti.search("用户喜欢吃什么水果")
        
        print("\n===== 时序字段验证 (水果偏好) =====")
        if not results:
            print("No results found.")
        
        for r in results:
            print(f"Fact: {r.fact}")
            print(f"  - valid_at: {getattr(r, 'valid_at', 'N/A')}")
            print(f"  - invalid_at: {getattr(r, 'invalid_at', 'N/A')}")
            print(f"  - created_at: {getattr(r, 'created_at', 'N/A')}")
            print("---")

        # 名字变更测试 (更明显的冲突)
        print("\nAdding name fact (Bob) at 2025-01-01...")
        await graphiti.add_episode(
            name="name_1",
            episode_body="My name is Bob.",
            source=EpisodeType.text,
            source_description="intro",
            reference_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        print("Adding name update (lice) at 2025-02-01...")
        await graphiti.add_episode(
            name="name_2",
            episode_body="I changed my name to Alice.",
            source=EpisodeType.text,
            source_description="intro update",
            reference_time=datetime(2025, 2, 1, tzinfo=timezone.utc),
        )
        
        print("Searching for 'What is my name'...")
        name_results = await graphiti.search("What is my name")
        print("\n===== 时序字段验证 (姓名变更) =====")
        for r in name_results:
            print(f"Fact: {r.fact}")
            print(f"  - valid_at: {getattr(r, 'valid_at', 'N/A')}")
            print(f"  - invalid_at: {getattr(r, 'invalid_at', 'N/A')}")
            print("---")
            
            
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await graphiti.close()
        print("Connection closed.")

if __name__ == "__main__":
    asyncio.run(main())

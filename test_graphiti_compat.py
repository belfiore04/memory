import os
import asyncio
from dotenv import load_dotenv
from graphiti_core import Graphiti
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.nodes import EpisodeType
from datetime import datetime, timezone

async def test_graphiti_compatibility():
    load_dotenv()
    api_key = os.getenv("DASHSCOPE_API_KEY")
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    print(f"Testing Graphiti with model: {os.getenv('ABILITY_MODEL')} and small_model: {os.getenv('SPEED_MODEL')}")
    
    try:
        llm_config = LLMConfig(
            api_key=api_key,
            model=os.getenv("ABILITY_MODEL"),
            small_model=os.getenv("SPEED_MODEL"),
            base_url=base_url,
        )
        llm_client = OpenAIGenericClient(config=llm_config)
        
        embedder = OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key=api_key,
                embedding_model="text-embedding-v4",
                embedding_dim=1024,
                base_url=base_url,
            )
        )
        
        driver = FalkorDriver(host="localhost", port=6380)
        
        graphiti = Graphiti(
            graph_driver=driver,
            llm_client=llm_client,
            embedder=embedder,
            cross_encoder=OpenAIRerankerClient(client=llm_client, config=llm_config),
        )
        
        print("Initialised. Adding episode...")
        current_time = datetime.now(timezone.utc)
        await graphiti.add_episode(
            name="test_episode",
            episode_body="User likes seafood and lives in Beijing.",
            source=EpisodeType.text,
            source_description="script_test",
            reference_time=current_time
        )
        print("✅ add_episode succeeded!")
        
    except Exception as e:
        print(f"❌ add_episode failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_graphiti_compatibility())

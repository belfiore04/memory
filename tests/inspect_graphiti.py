import asyncio
import os
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

async def inspect_graphiti():
    # 简单的 mock 配置，尽量复用 MemoryService 的初始化逻辑
    # 注意：这里需要 FalkorDB 运行中
    client = Graphiti("bolt://localhost:6380")
    
    print("Graphiti attributes:", dir(client))
    
    # 尝试查找 driver 或 graph 对象
    if hasattr(client, 'driver'):
        print("client.driver:", client.driver)
        print("client.driver attributes:", dir(client.driver))
    
    if hasattr(client, '_driver'):
        print("client._driver:", client._driver)
    
    if hasattr(client, 'graph'):
        print("client.graph:", client.graph)
        
    await client.close()

if __name__ == "__main__":
    asyncio.run(inspect_graphiti())

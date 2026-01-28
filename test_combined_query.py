import os
import asyncio
from dotenv import load_dotenv
from services.memory_service import MemoryService

async def test_combined_query():
    load_dotenv()
    service = MemoryService()
    driver = service.graphiti.driver
    
    print("\n--- 测试组合查询 (Episode + Relation) ---")
    
    # 策略 1: 查询所有 Episode
    query_episodes = "MATCH (e:Episodic) RETURN e.name, e.content, e.created_at"
    try:
        records, _, _ = await driver.execute_query(query_episodes)
        print(f"Episodes found: {len(records)}")
        for r in records:
            print(f"Episode: {r['e.name']} | Content: {r['e.content']}")
    except Exception as e:
        print(f"Episode query failed: {e}")

    # 策略 2: 查询业务关系 (注意：Graphiti 的边属性可能因版本而异)
    query_rels = "MATCH (n)-[r]->(m) WHERE type(r) <> 'MENTIONS' RETURN n.name, type(r), m.name, r.fact"
    try:
        records, _, _ = await driver.execute_query(query_rels)
        print(f"Business relations found: {len(records)}")
    except Exception as e:
        print(f"Relation query failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_combined_query())

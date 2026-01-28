import os
import asyncio
from dotenv import load_dotenv
from services.memory_service import MemoryService

async def check_edges():
    load_dotenv()
    service = MemoryService()
    driver = service.graphiti.driver
    
    print("\n--- 检查图数据库中的所有关系 (Edges) ---")
    
    # 查询所有关系及其属性
    query = """
    MATCH (n)-[r]->(m) 
    RETURN n.name as source, type(r) as relation_type, m.name as target, r.fact as fact
    LIMIT 20
    """
    try:
        records, _, _ = await driver.execute_query(query)
        print(f"找到 {len(records)} 条关系:")
        for i, r in enumerate(records):
            print(f"\n关系 {i+1}:")
            print(f"  {r['source']} --[{r['relation_type']}]--> {r['target']}")
            if r.get('fact'):
                print(f"  Fact: {r['fact']}")
    except Exception as e:
        print(f"查询失败: {e}")

if __name__ == "__main__":
    asyncio.run(check_edges())

import os
import asyncio
from dotenv import load_dotenv
from services.memory_service import MemoryService

async def diagnose_graphiti():
    load_dotenv()
    service = MemoryService()
    
    print("\n--- Graphiti 内部配置 ---")
    driver = service.graphiti.driver
    # 尝试获取图名称。在 falkordb-python 中，graph 对象的 'name' 属性是图名称
    # 但 Graphiti 包装了它。让我们看看 driver 里的东西。
    print(f"Driver Type: {type(driver)}")
    
    # 执行一个最通用的查询，不加任何限制
    query = "MATCH (n) RETURN n LIMIT 5"
    try:
        # FalkorDriver 的 execute_query 是异步的
        records, _, _ = await driver.execute_query(query)
        print(f"Total nodes found in current graph: {len(records)}")
        for i, r in enumerate(records):
            print(f"Node {i}: {r}")
            
        # 看看有没有关系
        query_rel = "MATCH ()-[r]->() RETURN type(r) LIMIT 5"
        records_rel, _, _ = await driver.execute_query(query_rel)
        print(f"Total relations found: {len(records_rel)}")
        for i, r in enumerate(records_rel):
            print(f"Rel {i}: {r}")

    except Exception as e:
        print(f"Query failed: {e}")

if __name__ == "__main__":
    asyncio.run(diagnose_graphiti())

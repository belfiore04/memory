import os
import asyncio
from dotenv import load_dotenv
from services.memory_service import MemoryService

async def inspect_nodes_detail():
    load_dotenv()
    service = MemoryService()
    driver = service.graphiti.driver
    
    print("\n--- 检查所有节点属性 ---")
    query = "MATCH (n) RETURN labels(n) as labels, properties(n) as props"
    try:
        records, _, _ = await driver.execute_query(query)
        for r in records:
            print(f"Labels: {r['labels']} | Props: {r['props']}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n--- 检查所有关系及其属性 ---")
    query_rel = "MATCH (n)-[r]->(m) RETURN type(r) as type, properties(r) as props, n.name as src, m.name as dst"
    try:
        records, _, _ = await driver.execute_query(query_rel)
        for r in records:
            print(f"Relation: {r['src']} --[{r['type']}]--> {r['dst']} | Props: {r['props']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_nodes_detail())

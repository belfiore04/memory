import os
import asyncio
from dotenv import load_dotenv
from services.memory_service import MemoryService

async def deep_graph_analysis():
    load_dotenv()
    service = MemoryService()
    driver = service.graphiti.driver
    
    print("=" * 80)
    print("=== Graphiti 深度图结构分析 ===")
    print("=" * 80)
    
    # 1. 查看所有 Entity 节点
    print("\n【1. 所有实体节点】")
    query = """
    MATCH (n:Entity)
    RETURN n.name as name, n.uuid as uuid, n.summary as summary
    ORDER BY n.name
    """
    records, _, _ = await driver.execute_query(query)
    for r in records:
        print(f"\n  实体: {r['name']}")
        print(f"    UUID: {r['uuid']}")
        print(f"    Summary: {r['summary'][:100] if r['summary'] else '(无)'}...")
    
    # 2. 查看所有 Edge（业务关系）
    print("\n\n【2. 所有业务关系边及其 fact】")
    query = """
    MATCH (n)-[r]->(m)
    WHERE type(r) <> 'MENTIONS'
    RETURN n.name as source, type(r) as rel, m.name as target, 
           r.fact as fact, r.uuid as uuid
    ORDER BY r.created_at DESC
    """
    records, _, _ = await driver.execute_query(query)
    for i, r in enumerate(records):
        print(f"\n  Edge {i+1}: {r['source']} --[{r['rel']}]--> {r['target']}")
        print(f"    Fact: {r['fact']}")
        print(f"    UUID: {r['uuid']}")
    
    # 3. 搜索"拌面"相关的所有边
    print("\n\n【3. 搜索包含'拌面'的所有边】")
    query = """
    MATCH (n)-[r]->(m)
    WHERE r.fact CONTAINS '拌面'
    RETURN n.name as source, m.name as target, r.fact as fact, r.uuid as uuid
    """
    records, _, _ = await driver.execute_query(query)
    print(f"找到 {len(records)} 条包含'拌面'的边:")
    for r in records:
        print(f"  - {r['source']} -> {r['target']}: {r['fact']}")
        print(f"    UUID: {r['uuid']}")
    
    # 4. 搜索"便利店"相关的所有边
    print("\n\n【4. 搜索包含'便利店'的所有边】")
    query = """
    MATCH (n)-[r]->(m)
    WHERE r.fact CONTAINS '便利店'
    RETURN n.name as source, m.name as target, r.fact as fact
    """
    records, _, _ = await driver.execute_query(query)
    print(f"找到 {len(records)} 条包含'便利店'的边:")
    for r in records:
        print(f"  - {r['source']} -> {r['target']}: {r['fact']}")
    
    # 5. 搜索"红烧牛肉"相关的边
    print("\n\n【5. 搜索包含'红烧牛肉'的所有边】")
    query = """
    MATCH (n)-[r]->(m)
    WHERE r.fact CONTAINS '红烧牛肉'
    RETURN n.name as source, m.name as target, r.fact as fact, r.uuid as uuid
    """
    records, _, _ = await driver.execute_query(query)
    print(f"找到 {len(records)} 条包含'红烧牛肉'的边:")
    for r in records:
        print(f"  - {r['source']} -> {r['target']}: {r['fact']}")
        print(f"    UUID: {r['uuid']}")
    
    # 6. 查看所有 Episodic（原始记忆片段）
    print("\n\n【6. 所有原始记忆片段 (Episodic)】")
    query = """
    MATCH (e:Episodic)
    RETURN e.name as name, e.content as content
    ORDER BY e.created_at DESC
    LIMIT 20
    """
    records, _, _ = await driver.execute_query(query)
    for r in records:
        print(f"  - {r['name']}: {r['content']}")

if __name__ == "__main__":
    asyncio.run(deep_graph_analysis())

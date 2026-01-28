import os
import asyncio
from dotenv import load_dotenv
from services.memory_service import MemoryService

async def detailed_graph_inspection():
    load_dotenv()
    service = MemoryService()
    driver = service.graphiti.driver
    
    print("=" * 60)
    print("=== Graphiti 图数据库详细检查 ===")
    print("=" * 60)
    
    # 1. 查询所有 Entity 节点
    print("\n【1. Entity 节点 (实体)】")
    query_nodes = """
    MATCH (n:Entity) 
    RETURN n.name as name, n.uuid as uuid, n.summary as summary, labels(n) as labels, n.created_at as created_at
    """
    try:
        records, _, _ = await driver.execute_query(query_nodes)
        print(f"共 {len(records)} 个实体节点:")
        for i, r in enumerate(records):
            print(f"\n  节点 {i+1}: {r['name']}")
            print(f"    UUID: {r['uuid']}")
            print(f"    Labels: {r['labels']}")
            print(f"    Summary: {r['summary'] or '(无)'}")
            print(f"    Created: {r['created_at']}")
    except Exception as e:
        print(f"查询失败: {e}")
    
    # 2. 查询所有 Episodic 节点 (原始记忆片段)
    print("\n\n【2. Episodic 节点 (原始记忆片段)】")
    query_episodes = """
    MATCH (e:Episodic) 
    RETURN e.name as name, e.content as content, e.source_description as source, e.created_at as created_at
    """
    try:
        records, _, _ = await driver.execute_query(query_episodes)
        print(f"共 {len(records)} 个 Episode:")
        for i, r in enumerate(records):
            print(f"\n  Episode {i+1}: {r['name']}")
            print(f"    Content: {r['content']}")
            print(f"    Source: {r['source']}")
            print(f"    Created: {r['created_at']}")
    except Exception as e:
        print(f"查询失败: {e}")
    
    # 3. 查询所有业务关系边 (排除 MENTIONS)
    print("\n\n【3. 业务关系边 (Edge / Fact)】")
    query_edges = """
    MATCH (n)-[r]->(m) 
    WHERE type(r) <> 'MENTIONS'
    RETURN n.name as source, type(r) as relation_type, m.name as target, 
           r.fact as fact, r.uuid as uuid, r.valid_at as valid_at, r.created_at as created_at
    """
    try:
        records, _, _ = await driver.execute_query(query_edges)
        print(f"共 {len(records)} 条业务关系:")
        for i, r in enumerate(records):
            print(f"\n  关系 {i+1}:")
            print(f"    {r['source']} --[{r['relation_type']}]--> {r['target']}")
            print(f"    Fact: {r['fact']}")
            print(f"    UUID: {r['uuid']}")
            print(f"    Valid At: {r['valid_at']}")
            print(f"    Created: {r['created_at']}")
    except Exception as e:
        print(f"查询失败: {e}")
    
    # 4. 查询 MENTIONS 引用关系
    print("\n\n【4. MENTIONS 引用关系 (Episode -> Entity)】")
    query_mentions = """
    MATCH (e:Episodic)-[r:MENTIONS]->(n:Entity)
    RETURN e.name as episode, n.name as entity
    """
    try:
        records, _, _ = await driver.execute_query(query_mentions)
        print(f"共 {len(records)} 条引用:")
        for r in records:
            print(f"  {r['episode']} --> {r['entity']}")
    except Exception as e:
        print(f"查询失败: {e}")

if __name__ == "__main__":
    asyncio.run(detailed_graph_inspection())

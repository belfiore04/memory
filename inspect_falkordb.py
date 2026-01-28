import os
from falkordb import FalkorDB
from dotenv import load_dotenv

def inspect_db():
    load_dotenv()
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", 6380))
    
    print(f"Connecting to FalkorDB at {host}:{port}...")
    try:
        db = FalkorDB(host=host, port=port)
        # Graphiti 默认使用 'graphiti' 作为图名称
        graph = db.select_graph("graphiti")
        
        print("\n--- 节点统计 ---")
        res = graph.query("MATCH (n) RETURN labels(n) as label, count(n) as count")
        for row in res.result_set:
            print(f"Label: {row[0]}, Count: {row[1]}")
            
        print("\n--- 关系统计 ---")
        res = graph.query("MATCH ()-[r]->() RETURN type(r) as type, count(r) as count")
        for row in res.result_set:
            print(f"Type: {row[0]}, Count: {row[1]}")

        print("\n--- 抽样查看 Entity 节点 ---")
        res = graph.query("MATCH (n:Entity) RETURN n.name, n.summary LIMIT 5")
        for row in res.result_set:
            print(f"Name: {row[0]}, Summary: {row[1]}")

        print("\n--- 抽样查看关系内容 (排除 MENTIONS) ---")
        res = graph.query("MATCH (n)-[r]->(m) WHERE type(r) <> 'MENTIONS' RETURN n.name, type(r), m.name, r.fact LIMIT 5")
        for row in res.result_set:
            print(f"{row[0]} --[{row[1]}]--> {row[2]} | Fact: {row[3]}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_db()

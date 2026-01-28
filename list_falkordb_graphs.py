import os
from falkordb import FalkorDB
from dotenv import load_dotenv

def list_graphs():
    load_dotenv()
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", 6380))
    
    print(f"Connecting to FalkorDB at {host}:{port}...")
    try:
        db = FalkorDB(host=host, port=port)
        # 尝试列出所有 key，FalkorDB 的图通常以 key 形式存在
        # 或者直接尝试默认的几个名字
        graphs = ["graphiti", "falkordb", "test", "default"]
        for g_name in graphs:
            g = db.select_graph(g_name)
            try:
                res = g.query("MATCH (n) RETURN count(n)")
                count = res.result_set[0][0]
                print(f"Graph '{g_name}': {count} nodes")
            except:
                print(f"Graph '{g_name}': Not found or query failed")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_graphs()

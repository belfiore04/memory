import asyncio
from dotenv import load_dotenv
from services.memory_service import MemoryService

async def test_search_with_more_results():
    load_dotenv()
    service = MemoryService()
    
    query = "诶 你知不知道我昨天在便利店买了什么"
    
    print(f"Query: {query}")
    print("=" * 60)
    
    # 增加 limit 到 10
    results = await service.search("1", query, limit=10)
    
    print(f"找到 {len(results)} 条结果:\n")
    for i, r in enumerate(results):
        print(f"{i+1}. {r['content']}")
        print(f"   UUID: {r['id']}")
        print()

if __name__ == "__main__":
    asyncio.run(test_search_with_more_results())

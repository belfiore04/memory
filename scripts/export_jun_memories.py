import asyncio
import json
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.memory_service import MemoryService

# Mock observe to avoid decorator errors if langfuse is not configured in this script context
# strictly speaking imports in memory_service might already import langfuse, so we might need to handle environment.
# But memory_service loads .env, so it should be fine.

async def main():
    user_id = "jun"
    print(f"Starting memory export for user: {user_id}...")
    
    try:
        service = MemoryService()
        # get_all fetches both edge-based memories and episodic memories
        data = await service.get_all(user_id)
        
        output_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exported_memories_jun.json")
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"✅ Successfully exported memories to: {output_file}")
        print(f"   - Total Items: {data.get('count', 0)}")
        print(f"   - Memories (Edges): {len(data.get('memories', []))}")
        print(f"   - Episodes: {len(data.get('episodes', []))}")
        
    except Exception as e:
        print(f"❌ Error exporting memories: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

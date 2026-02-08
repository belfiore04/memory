import asyncio
import json
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.memory_service import MemoryService
from services.chat_log_service import ChatLogService

async def main():
    print(f"Starting memory export for ALL users...")
    
    export_data = {}
    
    try:
        # 1. Get all user IDs from chat logs
        chat_service = ChatLogService()
        user_ids = chat_service.get_all_user_ids()
        print(f"Found {len(user_ids)} users in chat logs: {user_ids}")
        
        # 2. Add 'jun' explicitly just in case
        if "jun" not in user_ids:
            user_ids.append("jun")
            
        memory_service = MemoryService()
        
        for user_id in user_ids:
            print(f"Checking user: {user_id}...")
            try:
                # get_all fetches both edge-based memories and episodic memories
                mem_data = await memory_service.get_all(user_id)
                
                count = mem_data.get('count', 0)
                if count > 0:
                    print(f"  -> Found {count} items for {user_id}")
                    export_data[user_id] = mem_data
                else:
                    print(f"  -> No Graphiti memories found for {user_id}")
            except Exception as eu:
                print(f"  -> Error fetching for {user_id}: {eu}")

        # 3. Save to file
        output_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exported_memories_all.json")
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
            
        print(f"✅ Successfully exported memories to: {output_file}")
        print("Summary:")
        for uid, data in export_data.items():
            print(f"   - {uid}: {data.get('count')} items")
        
    except Exception as e:
        print(f"❌ Error during export: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

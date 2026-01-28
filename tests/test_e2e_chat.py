import requests
import json
import time

def test_chat_complete():
    user_id = "test_user_refactor"
    url = f"http://localhost:8000/chat/{user_id}/complete"
    
    # 1. Clear previous profile (optional, to be clean)
    try:
        requests.delete(f"http://localhost:8000/profile/{user_id}")
        requests.delete(f"http://localhost:8000/memory/{user_id}")
    except:
        pass

    # 2. Call /chat/complete directly with a message containing extractable info
    payload = {
        # "user_id": user_id,  # user_id is in URL now
        "messages": [
            {"role": "user", "content": "我叫张伟，是一名为期权交易员，最近市场波动很大让我很焦虑。"}
        ]
    }
    
    print(f"Sending request to {url}...")
    start_time = time.time()
    response = requests.post(url, json=payload)
    end_time = time.time()
    
    print(f"Response Code: {response.status_code}")
    print(f"Response Body: {response.text}")
    print(f"Time Taken: {end_time - start_time:.2f}s")
    
    if response.status_code == 200:
        print("✅ /chat/complete called successfully")
        
        # 3. Verify Profile Update
        print("Verifying profile update...")
        prof_res = requests.get(f"http://localhost:8000/profile/{user_id}")
        if prof_res.status_code == 200:
            slots = prof_res.json().get("slots", {})
            print(f"Current Slots: {json.dumps(slots, ensure_ascii=False, indent=2)}")
            
            if slots.get("nickname") == "张伟" and slots.get("occupation") == "期权交易员":
                print("✅ Profile extracted correctly!")
            else:
                print("❌ Profile mismatch.")
        
        # 4. Verify Memory Update
        print("Verifying memory update...")
        mem_res = requests.get(f"http://localhost:8000/memory/{user_id}")
        if mem_res.status_code == 200:
            memories = mem_res.json().get("memories", [])
            print(f"Current Memories Count: {len(memories)}")
            # Just check if count > 0, exact duplicate matching might be tricky depending on Qdrant state
            if len(memories) > 0:
                print("✅ Memory stored correctly!")
            else:
                print("⚠️ No memory stored (might vary based on extraction result).")
    else:
        print("❌ Failed to call /chat/complete")

if __name__ == "__main__":
    test_chat_complete()

import requests
import json
import time

def test_monologue_storage():
    url = "http://localhost:8000/chat/complete"
    user_id = "test_user_monologue"
    
    # 1. Clean up
    print("🧹 Cleaning up...")
    try:
        requests.delete(f"http://localhost:8000/memory/clear?user_id={user_id}")
        requests.post("http://localhost:8000/context/clear", json={"user_id": user_id})
    except Exception as e:
        print(f"Cleanup warning: {e}")

    # 2. Simulate Chat Complete with Monologue
    print("🚀 Sending Chat Complete request with Monologue...")
    
    user_input = "老板今天骂我了，好难过。"
    monologue = "用户遇到了职场挫折，情绪低落。我应该先表示共情，不要急着给建议。"
    reply = "抱抱你，被骂真的很难受吧？具体发生什么事了？"
    
    full_assistant_content = f"【内心独白】\n{monologue}\n\n【回复】\n{reply}"
    
    payload = {
        "user_id": user_id,
        "messages": [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": full_assistant_content}
        ]
    }
    
    response = requests.post(url, json=payload)
    print(f"Response Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.text}")
        return

    # 3. Verify Memory (LTM)
    print("\n🔍 Verifying Long Term Memory...")
    # Give Qdrant a moment to index if needed
    time.sleep(1)
    
    mem_res = requests.get(f"http://localhost:8000/memory/list?user_id={user_id}")
    memories = mem_res.json().get("memories", [])
    
    found_monologue = False
    for mem in memories:
        content = mem.get("content", "")
        print(f"- Memory Item: {content}")
        # 搜索独白中的关键部分，或者记录标识
        if ("ANU" in content or "内心想法" in content or "心理记录" in content) and monologue[:10] in content:
            found_monologue = True
            print("  ✅ Found Monologue in LTM!")
            
    if not found_monologue:
        print("  ❌ Monologue NOT found in LTM.")

    # 4. Verify Context (STC)
    print("\n🔍 Verifying Short Term Context...")
    ctx_res = requests.get(f"http://localhost:8000/context/get?user_id={user_id}")
    history = ctx_res.json().get("history", [])
    
    # Check the last assistant message
    if history:
        last_msg = history[-1]
        print(f"- Last Message Role: {last_msg.get('role')}")
        content = last_msg.get('content', '')
        # print(f"- Content: {content}")
        
        if "【内心独白】" in content and monologue in content:
            print("  ✅ Full content (including Monologue) found in STC!")
        else:
            print("  ❌ Monologue parsing missing in STC (Wait, STC should store RAW message).")
    else:
        print("  ❌ STC is empty.")

if __name__ == "__main__":
    test_monologue_storage()

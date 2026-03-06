import pytest

import asyncio
import uuid
import httpx
import time
import sys

BASE_URL = "http://localhost:8000"

@pytest.mark.asyncio
async def test_polling_e2e():
    print("=" * 60)
    print("🚀 Starting E2E Memory Polling Test")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. 注册/登录获取 Token
        print("[Step 1] Registering/Logging in...")
        test_username = f"test_user_{uuid.uuid4().hex[:8]}"
        test_password = "password"
        
        # 先试着注册
        await client.post(f"{BASE_URL}/auth/register", json={
            "username": test_username,
            "password": test_password
        })

        login_data = {
            "username": test_username,
            "password": test_password
        }
        # OAuth2PasswordRequestForm 要求使用 form-data
        login_resp = await client.post(f"{BASE_URL}/auth/login", data=login_data)
        
        if login_resp.status_code != 200:
            print(f"❌ Login failed: {login_resp.status_code} {login_resp.text}")
            return
        
        token = login_resp.json()["access_token"]
        user_id = login_resp.json()["user_id"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"✅ Logged in. User ID: {user_id}")

        # 2. 准备请求标识
        request_id = str(uuid.uuid4())
        print(f"[Step 2] Prepared Request ID: {request_id}")

        # 3. 异步并发：主请求 + 轮询
        print("[Step 3] Launching Concurrent Tasks...")
        
        results = {
            "polling_done": False,
            "polling_data": None,
            "interact_done": False,
            "interact_reply": None
        }

        async def monitor_memory():
            print("[Polling Task] Started.")
            start_poll = time.time()
            # 轮询最多持续 20 秒
            for i in range(40):
                try:
                    p_resp = await client.get(f"{BASE_URL}/chat/polling/{request_id}/memory")
                    if p_resp.status_code == 200:
                        data = p_resp.json()
                        status = data["status"]
                        print(f"[Polling Task] T+{time.time()-start_poll:.1f}s | Status: {status}")
                        
                        if status == "done":
                            results["polling_done"] = True
                            results["polling_data"] = data["data"]
                            print(f"🔥 [Polling Task] Memory retrieved early!")
                            return
                    elif p_resp.status_code == 404:
                         # 还没进入缓存系统，继续等
                         pass
                    else:
                        print(f"[Polling Task] Unexpected error: {p_resp.status_code}")
                except Exception as e:
                    print(f"[Polling Task] Error: {e}")
                
                await asyncio.sleep(0.5)

        async def main_interact():
            print("[Interact Task] Sending POST request...")
            start_interact = time.time()
            i_resp = await client.post(
                f"{BASE_URL}/chat/{user_id}/interact",
                json={
                    "user_query": "我是一只小青蛙，你能记住我是谁吗？",
                    "request_id": request_id
                },
                headers=headers
            )
            results["interact_done"] = True
            if i_resp.status_code == 200:
                results["interact_reply"] = i_resp.json()["reply"]
                print(f"✅ [Interact Task] Completed in {time.time()-start_interact:.1f}s")
            else:
                print(f"❌ [Interact Task] Failed: {i_resp.status_code} {i_resp.text}")

        # 并发执行
        await asyncio.gather(monitor_memory(), main_interact())

        # 4. 最终验证
        print("\n" + "=" * 60)
        print("📊 Test Summary:")
        if results["polling_done"]:
            print("✅ Memory Polling: SUCCESS (Got data before main response)")
            memories = results["polling_data"].get("memories", [])
            print(f"   Found {len(memories)} memory items.")
        else:
            print("❌ Memory Polling: FAILED (Never hit 'done' status)")

        if results["interact_done"] and results["interact_reply"]:
            print("✅ Chat Interaction: SUCCESS")
            print(f"   AI Reply (partial): {results['interact_reply'][:50]}...")
        else:
            print("❌ Chat Interaction: FAILED")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_polling_e2e())

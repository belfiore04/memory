import pytest

import asyncio
import uuid
import httpx
import time
import sys

BASE_URL = "http://localhost:8000"

@pytest.mark.asyncio
async def test_polling():
    # 获取 token（先尝试登录，失败则使用 mock）
    token = "mock_token"
    try:
        async with httpx.AsyncClient() as login_client:
            login_resp = await login_client.post(
                f"{BASE_URL}/auth/login",
                data={"username": "test_user", "password": "password"}
            )
            if login_resp.status_code == 200:
                token = login_resp.json()["access_token"]
    except Exception:
        pass
    # 1. 准备 Request ID 和 查询
    request_id = str(uuid.uuid4())
    user_query = "我是谁"  # 简单的查询，希望能触发记忆
    user_id = "test_user_polling"
    
    # 2. 启动 Polling 任务
    monitoring = True
    
    async def monitor_memory():
        print(f"[Polling] Start monitoring for {request_id}")
        while monitoring:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"{BASE_URL}/chat/polling/{request_id}/memory")
                    
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")
                    print(f"[Polling] Status: {status}")
                    
                    if status == "done":
                        print(f"[Polling] Memory Retrieved! Content: {data.get('data')}")
                        return True
            except httpx.TPSError:
                pass
            except Exception as e:
                print(f"[Polling] Error: {e}")
            
            await asyncio.sleep(0.5)
        return False

    # 3. 发送主 Chat 请求
    print(f"[Main] Sending chat request with request_id={request_id}")
    
    # 将 polling 任务放进后台
    poll_task = asyncio.create_task(monitor_memory())
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 获取 token (如果需要模拟鉴权)
        headers = {"Authorization": f"Bearer {token}"}
        
        start_time = time.time()
        resp = await client.post(
            f"{BASE_URL}/chat/{user_id}/interact", 
            json={
                "user_query": user_query,
                "request_id": request_id
            },
            headers=headers
        )
        end_time = time.time()
        
    monitoring = False
    await poll_task
    
    if resp.status_code == 200:
        print(f"[Main] Chat Request Completed in {end_time - start_time:.2f}s")
        print(f"[Main] Reply: {resp.json().get('reply')[:50]}...")
    else:
        print(f"[Main] Chat Request Failed: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_polling())


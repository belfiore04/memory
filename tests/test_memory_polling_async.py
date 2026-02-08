
import asyncio
import uuid
import httpx
import time
import sys

BASE_URL = "http://localhost:8000"

async def test_polling(token: str):
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

async def main():
    # 简单登录获取 Token (如果有的话，或者如果你本地关闭了鉴权)
    # 假设本地需要 Bearer Token，这里你需要填入一个有效的，或者先登录
    # 为了简化，我们假设可以通过 login 获取，或者你可以手动填入
    # 此处省略登录步骤，假设验证脚本在无鉴权或使用已知 Token 环境下运行
    # 请手动替换下面的 Token 如果需要
    token = "mock_token" 
    
    # 尝试登录获取 Token (复用之前的 login 逻辑)
    async with httpx.AsyncClient() as client:
        login_resp = await client.post(
            f"{BASE_URL}/auth/login",
            data={"username": "test_user", "password": "password"}
        )
        if login_resp.status_code == 200:
            token = login_resp.json()["access_token"]
            print(f"[Setup] Got token: {token[:10]}...")
        else:
            print("[Setup] Login failed, trying to create user or use mock token")
    
    await test_polling(token)

if __name__ == "__main__":
    asyncio.run(main())

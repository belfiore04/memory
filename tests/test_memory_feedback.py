from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
import json
import logging
import time

# 导入 app 和依赖
from main import app
from routers.chat import (
    get_memory_service, 
    get_trace_service, 
    get_extraction_agent,
    get_context_service,
    get_profile_service,
    get_chat_log_service
)

client = TestClient(app)

# 1. Mock ExtractionAgent (关键：模拟提取出内容)
mock_extraction_agent = MagicMock()
mock_extraction_agent.analyze_query.return_value = {
    "memory_items": [{"content": "用户今天心情不错", "type": "fact"}],
    "slot_updates": []
}

# 2. Mock MemoryService & Others
mock_memory_service = AsyncMock()
mock_context_service = MagicMock()
mock_profile_service = MagicMock()
mock_chat_log_service = MagicMock()
async def mock_retrieve(user_id, query):
    return {"memories": [], "should_retrieve": False}
mock_memory_service.retrieve = mock_retrieve

async def mock_generate_res(messages, response_format=None):
    m = MagicMock()
    m.content = "很高兴听到你心情好！"
    m.token_usage.dict.return_value = {"total": 100}
    return m
mock_memory_service.llm_client.generate_response = mock_generate_res

# Dependency Overrides
app.dependency_overrides[get_extraction_agent] = lambda: mock_extraction_agent
app.dependency_overrides[get_memory_service] = lambda: mock_memory_service
app.dependency_overrides[get_context_service] = lambda: mock_context_service
app.dependency_overrides[get_profile_service] = lambda: mock_profile_service
app.dependency_overrides[get_chat_log_service] = lambda: mock_chat_log_service

def test_memory_feedback_loop():
    # 账号逻辑 (使用之前测试过的 jun 账号或重新注册)
    username = f"feedback_test_{int(time.time())}"
    client.post("/auth/register", json={"username": username, "password": "password"})
    login_resp = client.post("/auth/login", data={"username": username, "password": "password"})
    token = login_resp.json()["access_token"]
    user_id = login_resp.json()["user_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # A. 调用 Interact
    print("Step A: Calling Interact...")
    resp = client.post(
        f"/chat/{user_id}/interact",
        json={"user_query": "我今天心情很好"},
        headers=headers
    )
    if resp.status_code != 200:
        print(f"FAILED: {resp.status_code} - {resp.text}")
    assert resp.status_code == 200
    trace_id = resp.json()["debug_info"]["trace_id"]
    print(f"Trace ID: {trace_id}")
    # B. 手动触发后台任务 (因为 TestClient 的 BackgroundTask 在 Mock 环境下有时难以跨线程轮询)
    print("Step B: Manually triggering background task as a unit test...")
    from routers.chat import _process_chat_background
    import asyncio
    
    # 构造 chat_msgs
    chat_msgs = [
        {"role": "user", "content": "我今天心情很好"},
        {"role": "assistant", "content": "很高兴听到你心情好！"}
    ]
    
    print(f"DEBUG: Triggering background task with trace_id={trace_id}")
    # 直接运行后台任务函数 (注入 Mock Services)
    asyncio.run(_process_chat_background(
        user_id=user_id,
        messages=chat_msgs,
        trace_id=trace_id,
        context_service=mock_context_service,
        extraction_agent=mock_extraction_agent,
        profile_service=mock_profile_service,
        memory_service=mock_memory_service,
        trace_service=get_trace_service() # 记忆必须存入真实的 Trace DB 才能被后续接口查到
    ))
    print("DEBUG: Background task finished.")

    # C. 轮询查询 Trace 结果
    print("Step C: Polling Trace...")
    for i in range(3):
        trace_resp = client.get(f"/chat/trace/{trace_id}", headers=headers)
        data = trace_resp.json()
        if data.get("new_memories"):
            print(f"Success! Found memories: {data['new_memories']}")
            assert "用户今天心情不错" in data["new_memories"]
            return
        time.sleep(1)
    
    assert False, "Timeout: Memories not found in Trace"

if __name__ == "__main__":
    test_memory_feedback_loop()

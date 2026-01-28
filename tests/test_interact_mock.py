# import pytest (removed)
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
import json
import logging
from typing import Dict, Any

# 导入 app 和依赖
from main import app
from routers.chat import get_memory_service, get_chat_log_service, get_context_service

logger = logging.getLogger(__name__)

client = TestClient(app)

# Mock Services
mock_memory_service = AsyncMock()
mock_chat_log_service = MagicMock()
mock_context_service = MagicMock()

# Setup Mock behavior
async def mock_retrieve(user_id, query):
    return {
        "should_retrieve": True,
        "memories": [{"content": "量子纠缠就像两颗心灵感应的骰子。"}],
        "episodes": []
    }
mock_memory_service.retrieve = mock_retrieve

async def mock_generate_response(messages, response_format=None):
    mock_resp = MagicMock()
    mock_resp.content = "量子纠缠可以比喻为......"
    mock_resp.token_usage.dict.return_value = {"prompt": 100, "completion": 50}
    return mock_resp
mock_memory_service.llm_client.generate_response = mock_generate_response

# Dependency Overrides
app.dependency_overrides[get_memory_service] = lambda: mock_memory_service
app.dependency_overrides[get_chat_log_service] = lambda: mock_chat_log_service
app.dependency_overrides[get_context_service] = lambda: mock_context_service

def test_interact_flow():
    # 1. Mock Login (AuthService is real but uses SQLite which is file based, fine)
    # We might need to mock AuthService if it fails too. 
    # Actually, let's try to mock existing user data to skip login.
    # Or just use the real login since we fixed passlib.
    
    # 注册用户
    username = "mock_user_001"
    client.post("/auth/register", json={"username": username, "password": "password"})
    login_resp = client.post("/auth/login", data={"username": username, "password": "password"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    user_id = login_resp.json()["user_id"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Interact
    resp = client.post(
        f"/chat/{user_id}/interact",
        json={"user_query": "Test Query"},
        headers=headers
    )
    
    if resp.status_code != 200:
        print(resp.text)
        
    assert resp.status_code == 200
    data = resp.json()
    
    # 3. Verify
    assert "量子纠缠" in data["reply"]
    assert data["debug_info"]["trace_id"]
    assert data["debug_info"]["latency"]["llm_generation"] >= 0
    
    print("Test passed!")

if __name__ == "__main__":
    test_interact_flow()

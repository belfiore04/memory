from shared.auth import auth
# import pytest (removed)
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
import json
import logging
from typing import Dict, Any

# 导入 app 和依赖
from main import app
from core_graph.routers.chat import get_memory_service, get_chat_log_service, get_context_service

logger = logging.getLogger(__name__)

import os
# Mock dependencies to avoid actual service instantiation
import sys
sys.modules['openai'] = AsyncMock()
sys.modules['langfuse.openai'] = AsyncMock()

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
app.dependency_overrides[auth.get_current_user] = lambda: {"id": "mock_user", "username": "mock_user_001"}

def test_interact_flow():
    # 1. Mock Login (AuthService is real but uses SQLite which is file based, fine)
    # We might need to mock AuthService if it fails too. 
    # Actually, let's try to mock existing user data to skip login.
    # Or just use the real login since we fixed passlib.
    
    # 注册用户 (跳过由于全局 DB 引起的实际请求，使用 mock user 测例)
    
    # 2. Interact
    resp = client.post(
        f"/chat/mock_user/interact",
        json={"user_query": "Test Query"}
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

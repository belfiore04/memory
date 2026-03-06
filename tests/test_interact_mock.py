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

# Mock LLM Client (模拟 chat.completions.create 返回)
mock_llm_client = MagicMock()
mock_completion_response = MagicMock()
mock_completion_response.choices = [MagicMock(message=MagicMock(content="量子纠缠可以比喻为两颗心灵感应的骰子。"))]
mock_completion_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

async def mock_create(*args, **kwargs):
    return mock_completion_response
mock_llm_client.chat.completions.create = mock_create

# Dependency Overrides
app.dependency_overrides[get_memory_service] = lambda: mock_memory_service
app.dependency_overrides[get_chat_log_service] = lambda: mock_chat_log_service
app.dependency_overrides[get_context_service] = lambda: mock_context_service
app.dependency_overrides[auth.get_current_user] = lambda: {"id": "mock_user", "username": "mock_user_001"}

@patch("core_graph.routers.chat.get_chat_llm_client", return_value=mock_llm_client)
@patch("core_graph.routers.chat.get_chat_model_name", return_value="mock-model")
def test_interact_flow(mock_model, mock_client):
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

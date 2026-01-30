import logging
import json
import sys
from unittest.mock import MagicMock

# [CRITICAL] Mock missing memory dependencies BEFORE importing services
sys.modules["graphiti_core"] = MagicMock()
sys.modules["services.memory_service"] = MagicMock()
sys.modules["services.memory_service"].MemoryService = MagicMock()

from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers.focus import router
from routers.auth import get_current_user
# 注意：FocusService 内部没有 import memory_service，应该安全
from services.focus_service import FocusService

# 1. 创建最小化 App
app = FastAPI()
app.include_router(router)

# 2. Mock Auth
def mock_get_current_user():
    return {"id": "test_user_iso", "username": "tester"}

app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)
USER_ID = "test_user_iso"

def test_focus_endpoints_isolated():
    print(f"\n>>> 开始测试 Focus 接口 (Isolated, User: {USER_ID})")
    
    # 0. 准备数据
    service = FocusService() # 依然使用真实的 SQLite (focus.db)
    service.clear_all_focus(USER_ID)
    service.add_focus(USER_ID, "ISO测试-关注点A")
    service.add_focus(USER_ID, "ISO测试-关注点B")
    service.save_whisper_suggestion(USER_ID, "ISO测试-耳语建议")
    
    # 1. 测试 GET /focus/{user_id}
    print("\n[1] Testing GET /focus list...")
    response = client.get(f"/focus/{USER_ID}")
    assert response.status_code == 200
    data = response.json()
    print(f"Response: {json.dumps(data, ensure_ascii=False)}")
    assert data["count"] == 2
    assert "ISO测试-关注点A" in data["focus_list"]
    
    # 2. 测试 GET /focus/{user_id}/whisper
    print("\n[2] Testing GET /focus whisper...")
    response = client.get(f"/focus/{USER_ID}/whisper")
    assert response.status_code == 200
    data = response.json()
    print(f"Response: {json.dumps(data, ensure_ascii=False)}")
    assert data["suggestion"] == "ISO测试-耳语建议"
    
    # 3. 测试 DELETE /focus/{user_id} (清空)
    print("\n[3] Testing DELETE /focus (Clear All)...")
    response = client.delete(f"/focus/{USER_ID}")
    assert response.status_code == 200
    print(f"Response: {json.dumps(response.json(), ensure_ascii=False)}")
    
    # 4. 验证清空结果
    print("\n[4] Verifying Clear...")
    response = client.get(f"/focus/{USER_ID}")
    data = response.json()
    assert data["count"] == 0
    
    print("\n>>> 所有 Focus 接口测试通过！✅")

if __name__ == "__main__":
    test_focus_endpoints_isolated()

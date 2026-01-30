import logging
import json
from fastapi.testclient import TestClient
from main import app
from routers.auth import get_current_user
from services.focus_service import FocusService

# 1. Mock Auth
def mock_get_current_user():
    return {"id": "test_user_api", "username": "tester"}

app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)
USER_ID = "test_user_api"

def test_focus_endpoints():
    print(f"\n>>> 开始测试 Focus 接口 (User: {USER_ID})")
    
    # 0. 准备数据
    service = FocusService()
    service.clear_all_focus(USER_ID) # 先清空
    service.add_focus(USER_ID, "API测试-关注点1")
    service.add_focus(USER_ID, "API测试-关注点2")
    service.save_whisper_suggestion(USER_ID, "API测试-耳语建议")
    
    # 1. 测试 GET /focus/{user_id}
    print("\n[1] Testing GET /focus list...")
    response = client.get(f"/focus/{USER_ID}")
    assert response.status_code == 200
    data = response.json()
    print(f"Response: {json.dumps(data, ensure_ascii=False)}")
    assert data["user_id"] == USER_ID
    assert data["count"] == 2
    assert "API测试-关注点1" in data["focus_list"]
    
    # 2. 测试 GET /focus/{user_id}/whisper
    print("\n[2] Testing GET /focus whisper...")
    response = client.get(f"/focus/{USER_ID}/whisper")
    assert response.status_code == 200
    data = response.json()
    print(f"Response: {json.dumps(data, ensure_ascii=False)}")
    assert data["suggestion"] == "API测试-耳语建议"
    assert data["is_consumed"] == False
    
    # 3. 测试 DELETE /focus/{user_id} (清空)
    print("\n[3] Testing DELETE /focus (Clear All)...")
    response = client.delete(f"/focus/{USER_ID}")
    assert response.status_code == 200
    print(f"Response: {json.dumps(response.json(), ensure_ascii=False)}")
    
    # 4. 验证清空结果
    print("\n[4] Verifying Clear...")
    response = client.get(f"/focus/{USER_ID}")
    data = response.json()
    print(f"Response: {json.dumps(data, ensure_ascii=False)}")
    assert data["count"] == 0
    assert data["focus_list"] == []
    
    print("\n>>> 所有 Focus 接口测试通过！✅")

if __name__ == "__main__":
    test_focus_endpoints()

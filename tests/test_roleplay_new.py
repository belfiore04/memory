import json
import os
import sys

# 确保项目根目录在 sys.path 中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from shared.auth.auth import get_current_user

# Mock current user dependency
def mock_get_current_user():
    return {"id": "test_rp_user", "username": "rp_tester"}

USER_ID = "test_rp_user"

def test_roleplay_new_flow():
    # 保存并清空之前的 overrides
    saved_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = mock_get_current_user

    client = TestClient(app)
    
    try:
        print(f"\n>>> 开始测试新 Roleplay 接口 (User: {USER_ID})")
        
        # 1. 设置角色内容 (模拟上传)
        print("\n[1] Testing POST /roleplay/{user_id}/character (Upload)...")
        char_content = """# 赛博诗人
你是一个生活在 2077 年的赛博诗人。
你说话总是带着赛博朋克的韵味，喜欢使用霓虹、义体、矩阵等词汇。
"""
        response = client.post(f"/roleplay/{USER_ID}/character", json={"content": char_content})
        assert response.status_code == 200
        assert response.json()["success"] is True
        print(f"Response: {response.json()}")
        
        # 2. 验证 Workspace 文件列表
        print("\n[2] Testing GET /roleplay/{user_id}/workspace...")
        response = client.get(f"/roleplay/{USER_ID}/workspace")
        assert response.status_code == 200
        files = response.json()
        filenames = [f["filename"] for f in files]
        print(f"Files in workspace: {filenames}")
        assert "CHARACTER.md" in filenames
        assert "SOUL.md" in filenames
        
        # 3. 验证 CHARACTER.md 内容
        print("\n[3] Testing GET /roleplay/{user_id}/workspace/CHARACTER.md...")
        response = client.get(f"/roleplay/{USER_ID}/workspace/CHARACTER.md")
        assert response.status_code == 200
        assert "赛博诗人" in response.json()["content"]
        
        # 4. 模拟对话 (Interact)
        # 注意：这可能会触发真实的 LLM 调用，取决于环境。
        # 在这里我们主要测试接口链路是否通。
        print("\n[4] Testing POST /roleplay/{user_id}/interact...")
        # 为了不产生高昂费用或依赖，我们预期它能走到调用层。
        # 如果测试环境没有 API KEY，这里可能会 503 或 500，
        # 但至少证明路由和 Service 逻辑是通的。
        response = client.post(f"/roleplay/{USER_ID}/interact", json={"user_query": "你是谁？"})
        print(f"Interaction Status: {response.status_code}")
        if response.status_code == 200:
             print(f"Reply: {response.json()['reply']}")
        else:
             print(f"Interaction response: {response.text}")
             # 允许 500/503 (如果是由于缺少 API KEY)，只要不是 404 就行
             assert response.status_code in [200, 500, 503]

        print("\n>>> 新 Roleplay 接口链路测试完成！✅")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved_overrides)

if __name__ == "__main__":
    test_roleplay_new_flow()

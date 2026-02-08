
import os
import sys
import requests
import json

# Add project root to sys.path
sys.path.append(os.getcwd())

def test_robust_feedback():
    user_id = "eee46254-78cd-46d6-9dbc-2470e47628e6"
    
    # 模拟从 Service 直接测试逻辑
    from services.feedback_service import FeedbackService
    service = FeedbackService()
    
    print("--- 1. 测试元数据拉取 ---")
    metadata = service.get_metadata()
    print(f"Metadata: {json.dumps(metadata, indent=2, ensure_ascii=False)}")
    assert "chat" in metadata
    assert "extraction" in metadata

    print("\n--- 2. 测试 Label 自动映射 (兼容模式) ---")
    # 使用 Label: "忘记了我想让他记住的东西"
    trace_id_1 = "test_trace_label"
    try:
        fb_id_1 = service.submit(
            user_id=user_id,
            trace_id=trace_id_1,
            score=5,
            categories=["忘记了我想让他记住的东西"]
        )
        # 验证存入数据库的是否已经是 Key
        fb_data = service.get_feedback(fb_id_1)
        print(f"Stored categories for Label input: {fb_data['categories']}")
        assert fb_data['categories'] == ["memory_forget"]
        print("✅ Label-to-Key mapping success!")
    except Exception as e:
        print(f"❌ Label mapping failed: {e}")

    print("\n--- 3. 测试 Key 正确提交 ---")
    # 使用 Key: "model_ooc"
    trace_id_2 = "test_trace_key"
    try:
        fb_id_2 = service.submit(
            user_id=user_id,
            trace_id=trace_id_2,
            score=4,
            categories=["model_ooc"]
        )
        fb_data = service.get_feedback(fb_id_2)
        print(f"Stored categories for Key input: {fb_data['categories']}")
        assert fb_data['categories'] == ["model_ooc"]
        print("✅ Key submission success!")
    except Exception as e:
        print(f"❌ Key submission failed: {e}")

    print("\n--- 4. 测试错误输入 ---")
    try:
        service.submit(
            user_id=user_id,
            trace_id="test_error",
            score=1,
            categories=["不存在的分类"]
        )
        print("❌ Should have failed but succeeded!")
    except ValueError as e:
        print(f"✅ Caught expected error for invalid category: {e}")

if __name__ == "__main__":
    test_robust_feedback()

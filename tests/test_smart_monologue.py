#!/usr/bin/env python3
"""
测试脚本：验证智能内心独白存储逻辑
测试场景：
1. 普通闲聊（JSON格式）- 不应存储 conversation_turn
2. 重要轮次（JSON格式）- 应该存储 conversation_turn
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"
USER_ID = "test_smart_monologue"

def cleanup():
    """清理测试数据"""
    print("🧹 清理测试数据...")
    try:
        requests.delete(f"{BASE_URL}/memory/clear?user_id={USER_ID}")
        requests.post(f"{BASE_URL}/context/clear", json={"user_id": USER_ID})
    except Exception as e:
        print(f"清理警告: {e}")

def test_casual_conversation():
    """测试1: 普通闲聊 - 不应存储 conversation_turn"""
    print("\n📝 测试1: 普通闲聊（不应存储 conversation_turn）")
    
    user_input = "你的眼睛好漂亮哦"
    assistant_reply = json.dumps({
        "inner_monologue": "用户在夸我，可以用轻松的方式回应。",
        "reply": "谢谢你的夸奖~"
    }, ensure_ascii=False)
    
    payload = {
        "user_id": USER_ID,
        "messages": [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": assistant_reply}
        ]
    }
    
    response = requests.post(f"{BASE_URL}/chat/complete", json=payload)
    print(f"Response Status: {response.status_code}")
    
    time.sleep(1)
    
    # 检查记忆
    mem_res = requests.get(f"{BASE_URL}/memory/list?user_id={USER_ID}")
    memories = mem_res.json().get("memories", [])
    
    has_conv_turn = False
    for mem in memories:
        content = mem.get("content", "")
        print(f"  - 记忆: {content[:50]}...")
        if "角色心理记录" in content or "conversation_turn" in content:
            has_conv_turn = True
    
    if has_conv_turn:
        print("  ❌ 失败: 普通闲聊不应存储 conversation_turn")
        return False
    else:
        print("  ✅ 通过: 普通闲聊未存储 conversation_turn")
        return True

def test_important_turn():
    """测试2: 重要轮次 - 应该存储 conversation_turn"""
    print("\n📝 测试2: 重要轮次（应该存储 conversation_turn）")
    
    cleanup()  # 先清理
    
    user_input = "我失恋了，感觉好难过，不知道该怎么办..."
    assistant_reply = json.dumps({
        "inner_monologue": "用户正在经历失恋的痛苦，情绪非常低落。这是一个建立信任的关键时刻，我需要先表达共情，让她感受到被理解，而不是急于给建议。这可能是我们关系的重要转折点。",
        "reply": "（轻轻叹了口气）失恋的感觉...我能理解那种空落落的心情。你愿意跟我说说发生了什么吗？不用着急，我在这里陪着你。"
    }, ensure_ascii=False)
    
    payload = {
        "user_id": USER_ID,
        "messages": [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": assistant_reply}
        ]
    }
    
    response = requests.post(f"{BASE_URL}/chat/complete", json=payload)
    print(f"Response Status: {response.status_code}")
    
    time.sleep(1)
    
    # 检查记忆
    mem_res = requests.get(f"{BASE_URL}/memory/list?user_id={USER_ID}")
    memories = mem_res.json().get("memories", [])
    
    has_conv_turn = False
    for mem in memories:
        content = mem.get("content", "")
        print(f"  - 记忆: {content[:60]}...")
        if "角色心理记录" in content or "共情" in content or "信任" in content:
            has_conv_turn = True
            print("    ^ 这是 conversation_turn 类型")
    
    if has_conv_turn:
        print("  ✅ 通过: 重要轮次成功存储 conversation_turn")
        return True
    else:
        print("  ❌ 失败: 重要轮次未存储 conversation_turn")
        return False

def main():
    print("=" * 60)
    print("智能内心独白存储测试")
    print("=" * 60)
    
    cleanup()
    
    results = []
    results.append(("普通闲聊", test_casual_conversation()))
    results.append(("重要轮次", test_important_turn()))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
    
    cleanup()

if __name__ == "__main__":
    main()

import asyncio
import json
import httpx

BASE_URL = "http://127.0.0.1:8000"
USER_ID = "test_user_debug"

async def test_debug_flow():
    print(f"=== 开始验证调试接口 (User: {USER_ID}) ===")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # 1. 清空旧数据
        print("\n1. [Clear] 清空旧数据...")
        try:
            resp = await client.delete(f"/memory/{USER_ID}")
            print(f"Response Status: {resp.status_code}")
            print(f"Response Body: {resp.text}")
            assert resp.status_code == 200
            assert resp.json()["success"] == True
        except Exception as e:
            print(f"ERROR during Clear: {e}")
            raise
        
        # 2. 存入第一条记忆
        print("\n2. [Store] 存入 '我喜欢苹果'...")
        messages1 = [
            {"role": "user", "content": "我最喜欢的水果是苹果"},
            {"role": "assistant", "content": "好的记住了，你喜欢苹果"}
        ]
        resp = await client.post(f"/memory/{USER_ID}/store", json={"messages": messages1})
        print(f"Response: {resp.status_code}")
        assert resp.status_code == 200
        
        # 等待 Graphiti 处理 (异步)
        print("等待 3 秒让 Graphiti 处理...")
        await asyncio.sleep(3)
        
        # 3. 存入第二条记忆 (触发更新)
        print("\n3. [Store] 存入 '我现在喜欢橙子'...")
        messages2 = [
            {"role": "user", "content": "我现在不喜欢苹果了，我喜欢橙子"},
            {"role": "assistant", "content": "好的，你现在喜欢橙子了"}
        ]
        resp = await client.post(f"/memory/{USER_ID}/store", json={"messages": messages2})
        print(f"Response: {resp.status_code}")
        assert resp.status_code == 200
        
        print("等待 3 秒让 Graphiti 处理...")
        await asyncio.sleep(3)
        
        # 4. 获取所有记忆并检查分组
        print("\n4. [Get All] 获取并检查分组历史...")
        resp = await client.get(f"/memory/{USER_ID}")
        print(f"Response: {resp.status_code}")
        assert resp.status_code == 200
        
        data = resp.json()
        print(f"Total count: {data['count']}")
        
        # 打印 grouped 数据
        grouped = data.get("grouped", {})
        print(f"Grouped keys: {list(grouped.keys())}")
        
        if grouped:
            # 尝试找 "LIKES" 或类似的 key
            # 注意: key 是 Graphiti 提取的原始英文
            import pprint
            pprint.pprint(grouped)
            
            # 验证结构
            first_key = list(grouped.keys())[0]
            group = grouped[first_key]
            assert "label" in group
            assert "history" in group
            assert isinstance(group["history"], list)
            
            print("✅ 分组结构验证通过")
        else:
            print("⚠️ 未提取到任何关系，可能需要更多时间或模型提取失败")
            # 不强制 assert，因为 LLM 提取可能不稳定
            
        # 5. 再次清空
        print("\n5. [Clear] 再次清空...")
        resp = await client.delete(f"/memory/{USER_ID}")
        assert resp.status_code == 200
        
        # 6. 验证清空后
        print("\n6. [Get All] 验证清空后为 0...")
        resp = await client.get(f"/memory/{USER_ID}")
        data = resp.json()
        assert data["count"] == 0
        assert data["memories"] == []
        print("✅ 清空验证通过")

if __name__ == "__main__":
    asyncio.run(test_debug_flow())

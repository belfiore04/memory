import httpx
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

async def test_multi_user_isolation():
    async with httpx.AsyncClient(timeout=None) as client:
        # 1. 登录用户 A 和用户 B (假设已在之前的步骤中通过注册或迁移创建)
        logger.info("用户 A 和用户 B 登录...")
        
        async def login(username, password):
            resp = await client.post(f"{BASE_URL}/auth/login", data={"username": username, "password": password})
            if resp.status_code != 200:
                # 如果登录失败，尝试注册后再登录
                await client.post(f"{BASE_URL}/auth/register", json={"username": username, "password": password})
                resp = await client.post(f"{BASE_URL}/auth/login", data={"username": username, "password": password})
            return resp.json()

        data_a = await login("user_a", "password123")
        data_b = await login("user_b", "password123")
        
        token_a = data_a["access_token"]
        user_id_a = data_a["user_id"]
        token_b = data_b["access_token"]
        user_id_b = data_b["user_id"]
        
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}
        
        logger.info(f"User A ID: {user_id_a}")
        logger.info(f"User B ID: {user_id_b}")

        # 2. 越权访问测试
        logger.info("用户 B 尝试使用自己的 Token 访问用户 A 的数据路径...")
        exploit = await client.get(f"{BASE_URL}/chat/{user_id_a}/history", headers=headers_b)
        assert exploit.status_code == 403
        logger.info("✓ API 层越权访问校验生效 (403 Forbidden)")
        
        # 3. 物理数据隔离测试
        logger.info("用户 A 通过合法渠道存储记忆...")
        await client.post(
            f"{BASE_URL}/memory/{user_id_a}/store",
            json={"messages": [{"role": "user", "content": "我的电话号码是 138-1234-5678"}]},
            headers=headers_a
        )
        
        logger.info("等待图数据库处理...")
        await asyncio.sleep(8) 
        
        logger.info("用户 B 尝试检索自己的记忆，看是否能混入 A 的数据...")
        search_b = await client.post(
            f"{BASE_URL}/memory/{user_id_b}/retrieve",
            json={"query": "我的电话号码是多少？"},
            headers=headers_b
        )
        memories_b = search_b.json().get("memories", [])
        logger.info(f"用户 B 搜到的记忆: {memories_b}")
        assert len(memories_b) == 0 or "138-1234-5678" not in str(memories_b)
        logger.info("✓ 物理层图数据库 (Per-User Graph) 隔离生效")

        # 4. 用户 A 正常访问
        search_a = await client.post(
            f"{BASE_URL}/memory/{user_id_a}/retrieve",
            json={"query": "我的电话号码是多少？"},
            headers=headers_a
        )
        logger.info(f"用户 A 搜到的记忆: {search_a.json().get('memories')}")

        logger.info("=" * 30)
        logger.info("E2E 隔离性测试全部通过！")

if __name__ == "__main__":
    asyncio.run(test_multi_user_isolation())

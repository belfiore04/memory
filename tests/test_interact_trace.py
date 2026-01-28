import httpx
import asyncio
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

async def test_interact_and_trace():
    async with httpx.AsyncClient(timeout=60.0) as client:
        import uuid
        random_suffix = str(uuid.uuid4())[:8]
        username = f"test_user_{random_suffix}"
        password = "password123"
        
        logger.info(f"注册并登录测试用户: {username}...")
        
        # 注册
        await client.post(f"{BASE_URL}/auth/register", json={"username": username, "password": password})
        
        # 登录
        resp = await client.post(f"{BASE_URL}/auth/login", data={"username": username, "password": password})
        
        if resp.status_code != 200:
             logger.error(f"最终登录失败: {resp.status_code} {resp.text}")
             return
        
        token = resp.json()["access_token"]
        user_id = resp.json()["user_id"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. 发起 Interact 请求 (替代 n8n)
        query = "请解释一下什么是“量子纠缠”，并尽量用通俗的比喻。"
        logger.info(f"发送交互请求: {query}")
        
        t0 = asyncio.get_event_loop().time()
        interact_resp = await client.post(
            f"{BASE_URL}/chat/{user_id}/interact",
            json={
                "user_query": query,
                # "system_prompt": "你可以自定义角色..." (可选)
            },
            headers=headers
        )
        t1 = asyncio.get_event_loop().time()
        
        if interact_resp.status_code != 200:
             logger.error(f"交互失败: {interact_resp.text}")
             return

        data = interact_resp.json()
        reply = data["reply"]
        debug_info = data["debug_info"]
        
        logger.info(f"收到回复 (耗时 {int((t1-t0)*1000)}ms): {reply[:50]}...")
        logger.info("=" * 30)
        logger.info("【Debug Info】")
        logger.info(json.dumps(debug_info, indent=2, ensure_ascii=False))
        logger.info("=" * 30)
        
        assert reply, "回复不能为空"
        assert debug_info["trace_id"], "Trace ID 必须存在"
        assert debug_info["latency"]["llm_generation"] > 0, "LLM 生成必须有耗时"
        
        # 3. 验证记忆是否存入 (需要等后台任务完成)
        logger.info("等待后台处理记忆 (5s)...")
        await asyncio.sleep(5)
        
        history_resp = await client.get(f"{BASE_URL}/chat/{user_id}/history", headers=headers)
        history = history_resp.json().get("history", [])
        
        # 验证最新的记录
        latest_msg = history[0]
        logger.info(f"最新历史: {latest_msg}")
        # 注意: 历史接口通常返回的是 user/assistant 对，或者最新的单条
        # 我们这里简单验证是否有新记录
        assert len(history) > 0
        
        logger.info("✓ Interact 接口全链路验证通过！")

if __name__ == "__main__":
    asyncio.run(test_interact_and_trace())

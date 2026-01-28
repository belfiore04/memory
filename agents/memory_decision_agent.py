"""
Memory Decision Agent
负责判断是否需要检索/存储记忆
"""

import os
import json
import logging
from typing import Dict, List, Tuple
from openai import OpenAI
from dotenv import load_dotenv
from langfuse import observe

logger = logging.getLogger(__name__)

# ==================== Prompt 定义 ====================

SHOULD_RETRIEVE_PROMPT = """你是一个记忆检索决策助手。你的任务是判断【用户问题的类型】是否需要去记忆库中检索信息。

【重要】你不需要知道记忆库里有没有相关信息，你只需要根据问题本身的特征来判断。
- 如果问题看起来是在询问过去的事、用户的偏好、或个人信息 → 需要检索
- 如果问题是通用知识问答或闲聊 → 不需要检索

【需要检索的问题类型】
1. 询问过去发生的事（"我上次..."、"之前..."、"还记得..."）
2. 测试/验证记忆（"你知不知道我..."、"你还记得...吗"、"我跟你说过..."）
3. 询问用户偏好/习惯（"我喜欢吃什么"、"我平时..."）
4. 包含时间指示词指向过去（"昨天"、"上周"、"之前"、"以前"）
5. 询问用户个人信息（"我的生日"、"我叫什么"）

【不需要检索的问题类型】
1. 通用知识问答（"什么是量子力学"）
2. 闲聊/打招呼（"你好"、"早上好"）
3. 用户在主动讲述新事情（不是在问）

请只返回 JSON：{"should_retrieve": true/false, "reason": "判断原因"}"""

SHOULD_STORE_PROMPT = """你是一个记忆管理助手。判断这段对话是否值得存入长期记忆。

【值得存储的内容】
1. 用户的个人偏好（喜欢/不喜欢什么）
2. 用户的个人信息（生日、职业、家庭情况等）
3. 重要的经历或事件（发生了什么事）
4. 用户明确要求记住的事情
5. 对理解用户有帮助的信息

【不需要存储的内容】
1. 纯粹的闲聊（"哈哈哈"、"嗯嗯"）
2. 与用户个人无关的知识问答
3. 临时性、一次性的信息
4. 重复的、已经存储过的信息

请只返回 JSON 格式：{"should_store": true/false, "reason": "判断原因"}"""


class MemoryDecisionAgent:
    """记忆决策 Agent - 判断是否需要检索/存储记忆"""
    
    def __init__(self):
        load_dotenv()
        logger.info("初始化记忆决策 Agent (MemoryDecisionAgent)")
        
        # 初始化 OpenAI 客户端
        dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        dashscope_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.client = OpenAI(api_key=dashscope_api_key, base_url=dashscope_base_url)
        
        # 使用速度优先模型
        self.llm_model = os.getenv("SPEED_MODEL", "qwen-flash")
    
    def should_retrieve(self, query: str) -> Tuple[bool, str]:
        """
        判断是否需要检索记忆
        
        Args:
            query: 用户当前输入
            
        Returns:
            (should_retrieve: bool, reason: str)
        """
        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": SHOULD_RETRIEVE_PROMPT},
                    {"role": "user", "content": query}
                ],
                temperature=0.1,
                max_tokens=150
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 清理 JSON
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            
            result = json.loads(result_text)
            return bool(result.get("should_retrieve", False)), result.get("reason", "")
            
        except Exception as e:
            logger.error(f"[ShouldRetrieve] 判断失败: {str(e)}")
            # 出错时保守地返回 True，确保不会漏掉重要信息
            return True, f"判断出错，默认检索: {str(e)}"
    
    def should_store(self, messages: List[Dict[str, str]]) -> Tuple[bool, str]:
        """
        判断是否需要存储记忆
        
        Args:
            messages: 对话消息列表 [{"role": "user/assistant", "content": "..."}]
            
        Returns:
            (should_store: bool, reason: str)
        """
        # 将消息格式化为对话文本
        conversation = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        
        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": SHOULD_STORE_PROMPT},
                    {"role": "user", "content": f"请判断这段对话：\n\n{conversation}"}
                ],
                temperature=0.1,
                max_tokens=150
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 清理 JSON
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            
            result = json.loads(result_text)
            return bool(result.get("should_store", False)), result.get("reason", "")
            
        except Exception as e:
            logger.error(f"[ShouldStore] 判断失败: {str(e)}")
            # 出错时保守地返回 False，避免存储垃圾信息
            return False, f"判断出错，默认不存储: {str(e)}"


if __name__ == "__main__":
    # 简单测试
    agent = MemoryDecisionAgent()
    
    # 测试检索判断
    test_queries = [
        "你知不知道我昨天去便利店买了什么",
        "我喜欢吃什么",
        "什么是量子力学",
        "早上好",
    ]
    
    print("=== 测试检索判断 ===")
    for q in test_queries:
        should, reason = agent.should_retrieve(q)
        print(f"Query: {q}")
        print(f"  Should Retrieve: {should}")
        print(f"  Reason: {reason}\n")

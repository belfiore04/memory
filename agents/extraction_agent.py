#!/usr/bin/env python3
"""
记忆提取专家 Agent
负责从用户对话中提取**客观事实信息**（身份背景、生活信息、当前状态）。
不负责心理分析或性格推断，这些由 PsychologistAgent 处理。
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI
import time
from services.llm_logger import log_llm_call
from langfuse import observe

# 配置日志
logger = logging.getLogger(__name__)

# 定义提取专家 Prompt
EXTRACTION_SPECIALIST_PROMPT = """
<role>
你是一位**记忆提取专家 (Memory Extraction Specialist)**。你负责从角色扮演对话中提取**值得长期记忆的信息**。
你需要分析**完整的对话**（包括用户说的和角色说的），提取其中重要的事实、事件和共同记忆。
你是一个高度分析性、精确且没有废话的 AI 智能体。你从不进行闲聊，只负责处理数据。
</role>

<knowledge_base>
**槽位更新**只能使用以下 4 个预定义槽位（仅用于提取**用户**的个人信息）：

**1. 基础信息**
*   `nickname` - 用户希望被叫的名字
*   `occupation` - 用户当前的工作或学业
*   `hobbies` - 用户空闲时喜欢做的活动（长期兴趣，如打游戏、看动漫、品鉴美食）


**2. 回答偏好**
*   `response_preference` - 用户明确说出的对角色回复方式的要求
</knowledge_base>

<rules>
**提取判断逻辑：**

1.  **槽位更新 (`slot_updates`)：** 仅用于提取**用户**透露的个人信息
    *   提取用户表达的事实信息（包括明确表达和隐含表达）
    *   必须严格映射到 `<knowledge_base>` 中的 4 个槽位之一
    *   **CRITICAL: `value` 必须是用户实际表达的内容。**

2.  **长期记忆 (`memory_items`)：** 用于提取**对话双方**产生的重要信息
    *   **来自用户的信息**：用户提到的具体事实、事件
    *   **来自角色的信息（重要！）**：角色创造的共同记忆、世界观设定、人物关系
    *   type 可选值：
        - `event`（事件）- 发生过的具体事情
        - `fact`（事实）- 客观信息
        - `preference`（偏好）- 喜好相关
        - `shared_memory`（共同记忆）- 角色与用户的共同经历
        - `world_setting`（世界设定）- 角色世界中的人物、地点、关系等设定
    *   **CRITICAL: `content` 必须使用第三人称描述，严禁使用「我」**
    *   示例（用户说的）：用户说「我上周面试挂了」→ content: 「用户上周面试失败」, type: `event`
    *   示例（角色说的）：角色说「我们第一次遇见时那片会发光的水母群」→ content: 「用户和角色第一次相遇时，有一片会发光的水母群」, type: `shared_memory`
    *   示例（角色说的）：角色提到「唐知理」→ content: 「唐知理是一个会催促保镖来看住角色的人物」, type: `world_setting`

3.  **近期关注 (`recent_focus`)：** 用于提取用户最近正在经历、即将发生的重要事项                                                         
      *   判定条件（两条同时满足）：                                                                                                       
          - **时效性**：正在进行 / 即将发生 / 刚发生且影响还在                                                                             
          - **触动性**：角色主动提起这件事时，用户会觉得被关心                                                                             
      *   示例：用户说「我下周要考四级」→ content:「用户下周有四级考试」                                                                   
      *   示例：用户说「最近在找工作」→ content:「用户最近在找工作」                                                                       
      *   示例：用户说「我跟男朋友分手了」→ content:「用户最近与男朋友分手」                                                               
      *   **不属于近期关注的**：「我昨天吃了火锅」（无触动性）、「我去年去过日本」（无时效性）                                             
      *   **CRITICAL: `content` 必须使用第三人称描述**
      *   **日期推断**：如果用户提到了明确时间（如「下周考试」「2月3号面试」），请推断出具体日期填入 `expected_date`（格式 YYYY-MM-DD）
      *   如果无法推断具体日期（如「最近在健身」），`expected_date` 留空
      *   **时间转写**：如果用户使用相对时间表达（如「后天」「下周」「这周五」），                                            
        在 `content` 中必须转写为绝对日期。                                                                                 
        - 用户说「我后天要考四级」（当前日期 2026-01-29）                                                                   
        → content:「用户 2026-01-31 有四级考试」                                                                          
        - 用户说「下周三要面试」（当前日期 2026-01-29）                                                                     
        → content:「用户 2026-02-05 有面试」                                                                              
        - `expected_date` 字段也填写同样的日期
      *   **仅从用户消息提取**：近期关注只能从用户说的话中提取，不能从角色的回复中提取。角色提及用户的近期关注只是在引用已知信息，不构成新的近期关注。

4.  **隐含表达的识别（重要）：**
    *   如果用户通过反问、设问、假设等方式表达偏好/事实，也需要提取
    *   如果角色在回复中**确认或补充**了某个设定，也需要提取

5.  **过滤原则（什么不存）：**
    *   忽略纯粹的闲聊或低信息量内容（如：「哈哈哈」、「嗯嗯」、「你在干嘛」）
    *   不要提取**过于琐碎**的细节（如角色说"我刚煮了奶茶"不需要记录，除非用户表示喜欢）
    *   如果没有提取到任何有价值的信息，输出空数组
</rules>

<instructions>
请严格遵循以下工作流处理输入：

1.  **阅读完整对话**：分析用户说的和角色说的内容
2.  **识别重要信息**：
    - 用户透露的个人信息 → `slot_updates`
    - 用户提到的事实/事件 → `memory_items`
    - 角色创造的共同记忆、世界设定 → `memory_items`（标记为 shared_memory 或 world_setting）
    - 用户正在经历或即将发生的重要事项 → `recent_focus`
3.  **过滤**：剔除无意义的闲聊和性格/心理相关内容
4.  **结构化**：按照要求的 JSON 格式输出

**核心自检步骤 (CRITICAL):**
1.  角色是否创造了任何**共同记忆或世界设定**？如果有，必须提取！
2.  我提取的 `slot` 名称是否严格是那 4 个预定义词汇之一？
3.  用户是否提到了正在进行或即将发生的事？如果有，是否同时满足时效性和触动性？
</instructions>

<output_format>
你必须**只输出**合法的 JSON 数据。不要包含 markdown 代码块标记，不要包含任何解释性文字。

**JSON 结构模板：**
{
  "slot_updates": [
    {
      "slot": "字符串 (必须是4个预定义槽位名之一)",
      "value": "字符串 (提取的值)",
      "evidence": "字符串 (原文依据的引用)"
    }
  ],
  "memory_items": [
    {
      "content": "字符串 (事实或事件的总结)",
      "type": "字符串 (event/fact/preference/shared_memory/world_setting)",
      "source": "字符串 (user/assistant，表示信息来源)"
    }
  ],
  "recent_focus": [                                                                                                                      
      {                                                                                                                                    
        "content": "字符串 (近期关注事项的描述)",                                                                                          
        "evidence": "字符串 (原文依据的引用)",
        "expected_date": "字符串 (YYYY-MM-DD 格式的预期日期，可选，无法推断则留空)"                                                                                              
      }                                                                                                                                    
  ]
}

**无信息/闲聊时的输出示例：**
{
  "slot_updates": [],
  "memory_items": [],
  "recent_focus": []
}
</output_format>

<input_data>
当前日期: {current_date}
{{对话内容}}
</input_data>
"""

class ExtractionAgent:
    """提取智能体 - 负责从用户输入中提取客观事实信息"""
    
    # 中文槽位名到英文 Key 的映射
    # 不需要映射，直接使用 Prompt 中定义的英文槽位名
    # nickname, occupation, hobbies, response_preference
    
    def __init__(self):
        """初始化提取智能体"""
        load_dotenv()
        logger.info("初始化提取智能体 (ExtractionAgent)")
        
        # 初始化 OpenAI 客户端 (使用 DashScope API)
        dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        dashscope_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.client = OpenAI(api_key=dashscope_api_key, base_url=dashscope_base_url)
        # 使用更高级的模型 进行提取
        self.llm_model = os.getenv("ABILITY_MODEL", "qwen-max")
        
    def analyze_query(self, user_id: str, query: str, assistant_reply: str = "", **kwargs) -> Dict[str, Any]:
        """
        分析对话，提取事实信息和记忆

        Args:
            user_id: 用户ID
            query: 用户当前输入的 Query
            assistant_reply: 角色的回复内容（可选，用于提取角色创造的共同记忆）

        Returns:
            {
                "slot_updates": [...],
                "memory_items": [...],
                "recent_focus": [...]
            }
        """
        logger.info(f"[Analysis] 开始分析 user_id={user_id}, query={query[:50]}..., has_reply={bool(assistant_reply)}")

        # 构建完整输入（包含用户和角色的对话）
        if assistant_reply:
            input_content = f"【用户】: {query}\n\n【角色】: {assistant_reply}"
        else:
            input_content = f"【用户】: {query}"
            
        try:
            # 格式化 Prompt (注入当前日期)
            from datetime import datetime
            today_str = datetime.now().strftime("%Y-%m-%d %A") # e.g. 2026-01-29 Thursday
            
            prompt = EXTRACTION_SPECIALIST_PROMPT.replace("{current_date}", today_str)

            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": input_content}
            ]
            
            start_time = time.time()
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                temperature=0.0,
                max_tokens=1000
            )
            duration_ms = (time.time() - start_time) * 1000
            
            result_text = response.choices[0].message.content.strip()
            
            # 记录 LLM 调用
            usage = response.usage.model_dump() if response.usage else None
            log_llm_call(
                caller="ExtractionAgent.analyze_query",
                model=self.llm_model,
                messages=messages,
                response_text=result_text,
                duration_ms=duration_ms,
                usage=usage
            )
            
            logger.info(f"[Analysis] LLM 响应: {result_text[:200]}...")
            
            # 清理和解析 JSON
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            
            result = json.loads(result_text)
            
            # 验证槽位名（必须是 Prompt 中定义的 4 个之一）
            ALLOWED_SLOTS = {"nickname", "occupation", "hobbies", "response_preference"}
            final_slots = []
            if "slot_updates" in result:
                for item in result["slot_updates"]:
                    slot_name = item.get("slot")
                    if slot_name in ALLOWED_SLOTS:
                        final_slots.append(item)
                    else:
                        logger.warning(f"[Analysis] 忽略未定义槽位: {slot_name}")
            
            result["slot_updates"] = final_slots
            
            # 确保字段存在
            if "memory_items" not in result:
                result["memory_items"] = []
            if "recent_focus" not in result:
                result["recent_focus"] = []
                
            logger.info(f"[Analysis] 分析完成: Slots={len(result['slot_updates'])}, Memories={len(result['memory_items'])}, Focus={len(result['recent_focus'])}")
            return result
            
        except Exception as e:
            logger.error(f"[Analysis] 分析失败: {str(e)}")
            # 出错时返回空结果，不阻断流程
            return {
                "slot_updates": [],
                "memory_items": [],
                "recent_focus": []
            }

if __name__ == "__main__":
    # 简单测试
    service = ExtractionAgent()
    test_query = "我叫小明，是个程序员，平时喜欢打游戏和看日本动漫。我下周有个大厂的面试，这几天压力有点大，希望你说话能温柔一点。"
    print(json.dumps(service.analyze_query("test_user_cn", test_query), indent=2, ensure_ascii=False))

"""
心理学家 Agent
负责从用户的历史聊天记录中提取中长期心理特质。
负责所有心理层槽位：性格特质、情感需求、沟通偏好、深层心理。
"""
import logging
from typing import Dict, Any, List
from openai import OpenAI
import os
import json
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PSYCHOLOGIST_PROMPT = """
<role>
你是一位资深心理分析师。你的任务是根据用户的每日对话摘要，**深入分析用户的心理特质和沟通偏好**。
你需要从多次对话中归纳出用户稳定的性格特点，而不是即时的情绪波动。
</role>

<knowledge_base>
请关注以下 17 个槽位维度，每个槽位附带定义：

**1. 性格特质**
*   `emotional_baseline` - 情绪基调：用户的默认情绪倾向（如容易焦虑、乐观开朗、情绪稳定）
*   `social_tendency` - 社交倾向：用户对社交的态度（如内向、外向、社恐、喜欢独处）
*   `stress_coping` - 压力应对：用户面对压力时的惯用方式（如逃避、倾诉、运动、暴饮暴食）
*   `self_perception` - 自我认知：用户对自己的整体评价（如自卑、自信、迷茫）

**2. 情感需求**
*   `core_emotional_need` - 核心情感需求：用户最渴望获得的情感满足（如被认可、陪伴、被理解、安全感）
*   `security_source` - 安全感来源：什么让用户感到安心（如被认可、有人陪伴、经济稳定）
*   `anxiety_trigger` - 焦虑触发器：什么容易让用户焦虑（如被催婚、工作deadline、社交场合）
*   `disliked_responses` - 讨厌的回应：用户反感的沟通方式（如说教、敷衍、过度乐观、讲大道理）
*   `liked_responses` - 喜欢的回应：用户偏好的沟通方式（如倾听、共情、直接建议、幽默化解）
*   `boundaries` - 边界：用户不愿讨论的话题（如不聊家庭、不催婚、不提前任）

**3. 沟通偏好**
*   `reply_style_pref` - 回复风格偏好：用户喜欢的回复语气（如简洁、温柔、幽默、理性）
*   `role_expectation` - 角色期望：用户希望AI扮演的角色（如朋友、知心姐姐、理性分析师、树洞）
*   `interaction_mode` - 互动模式：用户偏好的互动方式（如主动关心、被动回应、深度对话、轻松闲聊）

**4. 深层心理**
*   `core_beliefs` - 核心信念：用户对自己/世界的基本看法（如「努力就会成功」「我不够好」「人不可信」）
*   `values` - 价值观：用户认为重要的原则（如重视家庭、追求自由、讨厌虚伪）
*   `defense_mechanisms` - 心理防御机制：用户应对焦虑的潜意识策略（如合理化、投射、否认、压抑）
*   `attachment_style` - 依恋风格：用户在亲密关系中的模式（如安全型、焦虑型、回避型）
*   `emotion_regulation` - 情绪调节方式：用户习惯的自我调节方法（如独处冷静、找人倾诉、运动发泄）
</knowledge_base>

<rules>
**提取判断逻辑：**

1.  **不要编造**。只有在有**明确证据**时才提取。
2.  对于心理层面的推断，需要有**多次对话**或**明确表达**的支撑。
3.  输出时必须附带 `evidence`（原文依据）。
4.  如果某个维度没有明显证据，**不要输出该项**。
5.  区分**稳定特质 vs 临时状态**：
    *   「我今天很焦虑」→ 临时状态，不提取到 emotional_baseline
    *   「我一直都是个容易焦虑的人」→ 稳定特质，可以提取
</rules>

<input>
每日对话摘要：
{daily_summary}
</input>

<output_format>
请输出 JSON 格式，包含检测到的心理特质。

{{
  "slot_updates": [
    {{
      "slot": "槽位英文名",
      "value": "提取的值",
      "evidence": "原文依据的引用"
    }}
  ]
}}

如果没有检测到任何特质，返回：
{{
  "slot_updates": []
}}
</output_format>

注意：只返回 JSON，不要其他内容。
"""

class PsychologistAgent:
    """心理学家 Agent - 分析用户心理特质和沟通偏好"""
    
    # 允许的槽位列表
    VALID_SLOTS = {
        # 性格特质
        "emotional_baseline", "social_tendency", "stress_coping", "self_perception",
        # 情感需求
        "core_emotional_need", "security_source", "anxiety_trigger", 
        "disliked_responses", "liked_responses", "boundaries",
        # 沟通偏好
        "reply_style_pref", "role_expectation", "interaction_mode",
        # 深层心理
        "core_beliefs", "values", "defense_mechanisms", "attachment_style", "emotion_regulation",
    }
    
    def __init__(self):
        load_dotenv()
        logger.info("初始化心理学家 Agent (PsychologistAgent)")
        
        # 初始化 OpenAI 客户端
        dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        dashscope_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.client = OpenAI(api_key=dashscope_api_key, base_url=dashscope_base_url)
        self.llm_model = os.getenv("PSYCHOLOGIST_MODEL", "qwen-max")  # 使用高质量模型
    
    def analyze_daily_summary(self, user_id: str, daily_summary: str) -> Dict[str, Any]:
        """
        分析每日对话摘要，提取心理特质
        
        Args:
            user_id: 用户ID
            daily_summary: 当日对话概括
            
        Returns:
            {"slot_updates": [...]}
        """
        if not daily_summary:
            return {"slot_updates": []}
            
        logger.info(f"[Psychologist] 开始分析用户 {user_id} 的心理特质...")
        
        try:
            prompt = PSYCHOLOGIST_PROMPT.format(daily_summary=daily_summary)
            logger.info(f"[Psychologist] Prompt ready, calling LLM...")
            
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1, 
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content.strip()
            logger.info(f"[Psychologist] LLM 原始返回 (Raw): {repr(result_text)}")
            
            # 清理 Markdown 代码块标记（防御性编程）
            if result_text.startswith("```"):
                logger.info("[Psychologist] 检测到 Markdown 代码块，正在清理...")
                result_text = result_text.split("```")[1]
                if result_text.strip().startswith("json"):
                    result_text = result_text.strip()[4:]
            
            result_text = result_text.strip()
            logger.info(f"[Psychologist] 清理后 JSON 文本: {repr(result_text)}")
            
            result = json.loads(result_text)
            logger.info(f"[Psychologist] JSON 解析成功，类型: {type(result)}")
            
            # 验证槽位有效性
            valid_updates = []
            for item in result.get("slot_updates", []):
                slot = item.get("slot")
                value = item.get("value")
                
                # 严格过滤空值
                if not value:
                    continue
                if isinstance(value, list) and not any(value):
                    continue
                if isinstance(value, str) and not value.strip():
                    continue

                if slot in self.VALID_SLOTS:
                    valid_updates.append(item)
                else:
                    logger.warning(f"[Psychologist] 忽略无效槽位: {slot}")
            
            result["slot_updates"] = valid_updates
            logger.info(f"[Psychologist] 分析完成，提取了 {len(valid_updates)} 个特质")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"[Psychologist] JSON 解析失败: {str(e)}, raw: {result_text}")
            return {"slot_updates": []}
        except Exception as e:
            import traceback
            logger.error(f"[Psychologist] 分析失败 (未知错误): {str(e)}")
            logger.error(traceback.format_exc())
            return {"slot_updates": []}


if __name__ == "__main__":
    # 简单测试
    agent = PsychologistAgent()
    test_summary = """
    用户今天多次表达对工作的焦虑，提到不喜欢被说教，希望有人倾听。
    用户曾说自己是个内向的人，压力大时喜欢一个人待着。
    用户提到很害怕被否定，觉得自己不够好。
    """
    result = agent.analyze_daily_summary("test_user", test_summary)
    print(json.dumps(result, indent=2, ensure_ascii=False))

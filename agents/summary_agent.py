"""
摘要 Agent
负责将当日对话压缩为结构化摘要，供心理学家 Agent 分析使用
"""
import os
import json
import logging
from typing import Dict, Any, List
from openai import OpenAI
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ==================== 示例 Prompt（占位，后续替换）====================
SUMMARY_PROMPT = """
你是一个对话摘要助手。请将以下对话整理成简洁的摘要，重点关注：
1. 用户提到的重要事件
2. 用户表达的情绪变化
3. 用户透露的个人信息
4. 对话中的关键转折点

对话内容：
{dialogue}

请输出 JSON 格式，不要包含 markdown 代码块标记：
{{
  "key_events": ["事件1", "事件2"],
  "emotional_changes": "情绪变化描述",
  "personal_info": ["信息1", "信息2"],
  "summary": "整体摘要文本（200字以内）"
}}

如果对话内容很少或无实质内容，请输出：
{{
  "key_events": [],
  "emotional_changes": "",
  "personal_info": [],
  "summary": "无有效对话内容"
}}
"""

class SummaryAgent:
    """摘要 Agent - 负责生成每日对话摘要"""
    
    def __init__(self):
        load_dotenv()
        logger.info("初始化摘要 Agent (SummaryAgent)")
        
        # 初始化 OpenAI 客户端
        dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        dashscope_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.client = OpenAI(api_key=dashscope_api_key, base_url=dashscope_base_url)
        self.llm_model = os.getenv("SUMMARY_MODEL", "qwen-turbo")  # 摘要用 turbo 即可，速度快
    
    def summarize(self, dialogue_logs: List[Dict]) -> Dict[str, Any]:
        """
        将对话日志压缩为结构化摘要
        
        Args:
            dialogue_logs: 对话记录列表 [{"role": "user/assistant", "content": "..."}]
            
        Returns:
            {
                "key_events": ["事件1", "事件2"],
                "emotional_changes": "情绪变化描述",
                "personal_info": ["信息1", "信息2"],
                "summary": "整体摘要文本"
            }
        """
        if not dialogue_logs:
            logger.warning("[Summary] 对话日志为空")
            return {
                "key_events": [],
                "emotional_changes": "",
                "personal_info": [],
                "summary": "无对话记录"
            }
        
        # 格式化对话
        dialogue_text = self._format_dialogue(dialogue_logs)
        
        logger.info(f"[Summary] 开始生成摘要，对话长度: {len(dialogue_text)} 字符")
        
        try:
            prompt = SUMMARY_PROMPT.format(dialogue=dialogue_text)
            
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 清理 JSON
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            
            result = json.loads(result_text)
            
            logger.info(f"[Summary] 摘要生成完成: {result.get('summary', '')[:50]}...")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"[Summary] JSON 解析失败: {str(e)}, raw: {result_text}")
            return {
                "key_events": [],
                "emotional_changes": "",
                "personal_info": [],
                "summary": result_text if result_text else "解析失败"
            }
        except Exception as e:
            logger.error(f"[Summary] 摘要生成失败: {str(e)}")
            return {
                "key_events": [],
                "emotional_changes": "",
                "personal_info": [],
                "summary": f"生成失败: {str(e)}"
            }
    
    def _format_dialogue(self, logs: List[Dict]) -> str:
        """格式化对话日志为文本"""
        lines = []
        for log in logs:
            role = "用户" if log.get("role") == "user" else "角色"
            content = log.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

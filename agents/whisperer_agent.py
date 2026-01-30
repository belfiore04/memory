#!/usr/bin/env python3
"""
耳语者 (Whisperer) Agent
幕后导演，负责观察对话流，结合用户画像和近期关注，
为下一轮回复生成隐秘的策略指导 (Initial Prompt Injection)。
"""

import os
import logging
import json
from typing import List, Dict, Optional, Any, Tuple
from dotenv import load_dotenv
from langfuse.openai import OpenAI as LangfuseOpenAI  # [NEW] 使用 Langfuse 封装的客户端
from services.llm_logger import log_llm_call

logger = logging.getLogger(__name__)

WHISPERER_PROMPT = """
<role>                                                                                                                                   
你是一个**信息筛选器 (Whisperer)**。                                                                                                     
你的职责是观察当前对话，从用户的近期关注和画像中，                                                                                       
挑选出下一轮对话中角色应该额外知道的信息。                                                                                               
你不生成回复，不指导角色怎么说话。                                                                                                       
你只决定：角色下一轮需要额外知道什么。                                                                                                   
</role>

<input_context>
1. **当前时间**: 现在的日期和时间
2. **用户画像**: 用户的基础信息、爱好兴趣、回答偏好、行为观察
3. **近期关注**: 用户最近正在经历或即将发生的重要事项（格式: [ID: x] 内容 (时间信息)）
4. **近期对话摘要**: 之前对话的摘要，提供近期对话的整体脉络
5. **对话历史**: 摘要之后到当前的详细对话记录（可附带消息时间）
</input_context>

<rules>                                                                                                                                                                                                                                    
  1. **克制**：如果当前对话不需要额外信息，返回空。                                                                                        
     不要强行注入。大部分轮次应该返回空。                                                                                                  
  2. **每次最多注入一条**：避免信息过载。                                                                                                  
  3. **注入时机判断**：                                                                                                                    
     - “最新一轮”的对话内容与某条近期关注/画像信息产生了关联 → 注入                                                                                    
     - 某条近期关注即将保存过期（如明天就考试了）→ 注入                                                                                        
     - 对话陷入闲聊，有自然切入点 → 可以注入                                                                                               
     - 对话正在深入某个话题 → 不要打断，返回空
    4. **注入时机判断**：                                                                                                   
     - 你的判断标准如下：                                                                                       
       a) 当前对话与该信息有语义关联（情绪、话题、场景相关）                                                              
       b) 该信息在chat_history中未被角色提及
       c) 当前时间很接近该信息的预期时间
       必须同时满足a 和 b 或者满足c 时，才进行注入                                                                                                                                                                                                                                    
     - chat_summary 仅用于理解背景，不作为注入触发条件
  4. **时效性判断**：
     - 如果某条近期关注即将到期（如明天、后天），优先级提高
</rules>

<output_format>
请输出 JSON 格式：
{{
    "inject": null 或 "字符串（要注入的信息，如：用户下周有四级考试）",
    "used_focus_id": null 或 整数ID（如果使用了某条近期关注，填入其ID；否则null）
}}
</output_format>

<current_time>
{current_time}
</current_time>

<user_profile>
{user_profile}
</user_profile>

<recent_focus>
{recent_focus}
</recent_focus>

<chat_summary>
{chat_summary}
</chat_summary>

<chat_history>
{chat_history}
</chat_history>
"""

class WhispererAgent:
    def __init__(self):
        load_dotenv()
        logger.info("初始化耳语者 Agent (WhispererAgent)")
        
        dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        dashscope_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        # [NEW] 使用 LangfuseOpenAI 以实现自动 Trace
        self.client = LangfuseOpenAI(api_key=dashscope_api_key, base_url=dashscope_base_url)
        # 使用高智商模型进行策略规划
        self.llm_model = os.getenv("ABILITY_MODEL", "qwen-max")

    def create_suggestion(self,
                          user_id: str,
                          profile: Dict,
                          active_focus: List[Dict],
                          chat_summary: str,
                          chat_history: List[Dict],
                          current_time: str = None) -> Tuple[Optional[str], Optional[int]]:
        """
        分析对话并生成建议
        Returns: (suggestion_str, focus_id)
        """
        # 1. 格式化输入
        # 简化 profile 显示
        profile_str = json.dumps(profile, ensure_ascii=False)
        
        # 格式化 focus (处理 Dict 列表)
        focus_lines = []
        if active_focus:
            for f in active_focus:
                # 兼容旧代码传入 List[str] 的情况
                if isinstance(f, str):
                    focus_lines.append(f"- {f}")
                else:
                    # 格式: "[ID: x] - 内容 (添加于: YYYY-MM-DD, 截止: YYYY-MM-DD)"
                    f_id = f.get('id', 'N/A')
                    line = f"[ID: {f_id}] - {f.get('content', '')}"
                    meta = []
                    if f.get('recorded_at'):
                        meta.append(f"添加于: {f['recorded_at']}")
                    if f.get('expected_date'):
                        meta.append(f"截止: {f['expected_date']}")
                    
                    if meta:
                        line += f" ({', '.join(meta)})"
                    focus_lines.append(line)
            focus_str = "\n".join(focus_lines)
        else:
            focus_str = "无"
        
        # 格式化最近几轮历史 (限制为最近 5 轮，即 10 个消息)
        recent_msgs = chat_history[-10:] if len(chat_history) > 10 else chat_history
        history_str = "\n".join([f"{m['role']}: {m['content']}" for m in recent_msgs])
        
        summary_str = chat_summary if chat_summary else "无"
        
        # 默认当前时间
        if not current_time:
            from datetime import datetime
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        prompt = WHISPERER_PROMPT.format(
            current_time=current_time,
            user_profile=profile_str,
            recent_focus=focus_str,
            chat_summary=summary_str,
            chat_history=history_str
        )
        
        try:
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "请根据以上信息，输出你的策略判断。"}
            ]
            
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                temperature=0.7, # 稍微高一点 creativity，产生更灵活的策略
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # [FIX] 激进清理：用正则提取 JSON 部分
            # [FIX] 激进清理：用正则提取 JSON 部分
            import re
            # 1. 去除 markdown 代码块
            raw_text = result_text # 备份原始文本用于调试
            result_text = re.sub(r'^```(?:json)?\s*', '', result_text)
            result_text = re.sub(r'\s*```$', '', result_text)
            result_text = result_text.strip()
            
            # 2. 解析 JSON
            try:
                result = json.loads(result_text)
                
                # 记录成功日志
                log_llm_call(
                    caller="WhispererAgent",
                    model=self.llm_model,
                    messages=messages,
                    response_text=raw_text, # 记录 LLM 原始输出
                    duration_ms=0
                )
            except json.JSONDecodeError as e:
                logger.error(f"[Whisperer] JSON解析失败: {e}\nRaw: {raw_text}")
                # 记录失败日志
                log_llm_call(
                    caller="WhispererAgent",
                    model=self.llm_model,
                    messages=messages,
                    response_text=raw_text,
                    duration_ms=0,
                    error=f"JSONDecodeError: {str(e)}"
                )
                return None, None

            # 3. 解析字段
            inject_value = result.get("inject")
            used_focus_id = result.get("used_focus_id")
            
            if isinstance(inject_value, str) and inject_value.strip():
                logger.info(f"[Whisperer] 决定注入: {inject_value}, SourceID: {used_focus_id}")
                return inject_value, used_focus_id
            else:
                logger.info("[Whisperer] 决定不注入")
                return None, None
                
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"[Whisperer] 系统异常: {str(e)}\nTraceback: {tb}")
            # 尝试记录最后的异常日志
            try:
                log_llm_call(
                    caller="WhispererAgent",
                    model=self.llm_model,
                    messages=messages,
                    response_text="Error occurred", 
                    duration_ms=0,
                    error=str(e)
                )
            except:
                pass
            return None, None

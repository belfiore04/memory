#!/usr/bin/env python3
"""
用户画像槽位定义

槽位分为两大类，由不同 Agent 负责提取：
- ExtractionAgent（事实层，12个槽位）：身份背景、生活信息、当前状态
- PsychologistAgent（心理层，17个槽位）：性格特质、情感需求、沟通偏好、深层心理
"""

from typing import Dict, List, Literal

# 覆盖策略类型
MergeStrategy = Literal["replace", "append", "llm_judge"]


# ============================================================================
# ExtractionAgent 负责的槽位（事实层，12个）
# ============================================================================
EXTRACTION_SLOTS: Dict[str, Dict] = {
    # ==================== 身份背景 (4) ====================
    "nickname": {
        "description": "称呼",
        "definition": "用户希望被叫的名字",
        "category": "身份背景",
        "merge_strategy": "replace",
        "examples": ["小明", "明明", "阿明"]
    },
    "age_range": {
        "description": "年龄段",
        "definition": "用户的大致年龄范围",
        "category": "身份背景",
        "merge_strategy": "replace",
        "examples": ["20-25岁", "大学生", "30出头"]
    },
    "occupation": {
        "description": "职业",
        "definition": "用户当前的工作或学业",
        "category": "身份背景",
        "merge_strategy": "replace",
        "examples": ["程序员", "学生", "自由职业"]
    },
    "life_status": {
        "description": "生活状态",
        "definition": "用户的居住/家庭状况",
        "category": "身份背景",
        "merge_strategy": "replace",
        "examples": ["独居", "和父母住", "刚毕业", "已婚有娃"]
    },
    
    # ==================== 生活信息 (5) ====================
    "hobbies": {
        "description": "爱好兴趣",
        "definition": "用户空闲时喜欢做的活动（长期兴趣）",
        "category": "生活信息",
        "merge_strategy": "append",
        "examples": ["养花", "打游戏", "看动漫", "健身", "品鉴美食"]
    },
    "preferences": {
        "description": "偏好",
        "definition": "用户喜欢/不喜欢的具体事物（食物、品牌、类型等）",
        "category": "生活信息",
        "merge_strategy": "append",
        "examples": ["爱吃辣", "不吃香菜", "喜欢海鲜意面", "偏爱日系风格"]
    },
    "daily_routine": {
        "description": "日常习惯",
        "definition": "用户的作息或生活规律",
        "category": "生活信息",
        "merge_strategy": "replace",
        "examples": ["夜猫子", "早起锻炼", "三餐不规律"]
    },
    "important_people": {
        "description": "重要关系",
        "definition": "用户提到的亲密的人",
        "category": "生活信息",
        "merge_strategy": "append",
        "examples": ["男朋友叫小王", "有个弟弟在上大学", "妈妈在老家"]
    },
    "health_status": {
        "description": "健康状态",
        "definition": "用户的身体/睡眠状况",
        "category": "生活信息",
        "merge_strategy": "replace",
        "examples": ["最近失眠", "有胃病", "身体健康"]
    },
    "response_preference": {
        "description": "回答偏好",
        "definition": "用户明确说出的对角色回复方式的要求",
        "category": "沟通偏好",
        "merge_strategy": "replace",
        "examples": ["不要太粘人", "多说点脏话", "叫我主人"]
    },
    
    # ==================== 当前状态 (4) ====================
    "recent_focus": {
        "description": "近期关注",
        "definition": "用户最近在忙的事情",
        "category": "当前状态",
        "merge_strategy": "replace",
        "examples": ["找工作", "考研", "减肥", "学习新技能"]
    },
    "recent_mood": {
        "description": "近期情绪",
        "definition": "用户最近的情绪状态",
        "category": "当前状态",
        "merge_strategy": "replace",
        "examples": ["低落", "焦虑", "平静", "兴奋"]
    },
    "recent_events": {
        "description": "近期事件",
        "definition": "用户最近发生的重要事件",
        "category": "当前状态",
        "merge_strategy": "append",
        "examples": ["刚分手", "升职了", "和家人吵架", "搬家"]
    },
    "goals": {
        "description": "目标愿望",
        "definition": "用户近期想做的事情",
        "category": "当前状态",
        "merge_strategy": "replace",
        "examples": ["想学吉他", "准备考研", "计划旅行"]
    },
}


# ============================================================================
# PsychologistAgent 负责的槽位（心理层，17个）
# ============================================================================
PSYCHOLOGIST_SLOTS: Dict[str, Dict] = {
    # ==================== 性格特质 (4) ====================
    "emotional_baseline": {
        "description": "情绪基调",
        "definition": "用户的默认情绪倾向",
        "category": "性格特质",
        "merge_strategy": "llm_judge",
        "examples": ["容易焦虑", "乐观开朗", "情绪稳定", "敏感"]
    },
    "social_tendency": {
        "description": "社交倾向",
        "definition": "用户对社交的态度",
        "category": "性格特质",
        "merge_strategy": "llm_judge",
        "examples": ["内向", "外向", "喜欢独处", "社恐"]
    },
    "stress_coping": {
        "description": "压力应对",
        "definition": "用户面对压力时的惯用方式",
        "category": "性格特质",
        "merge_strategy": "llm_judge",
        "examples": ["逃避", "倾诉", "运动", "睡觉", "暴饮暴食"]
    },
    "self_perception": {
        "description": "自我认知",
        "definition": "用户对自己的整体评价",
        "category": "性格特质",
        "merge_strategy": "llm_judge",
        "examples": ["自卑", "自信", "迷茫", "清醒"]
    },
    
    # ==================== 情感需求 (6) ====================
    "core_emotional_need": {
        "description": "核心情感需求",
        "definition": "用户最渴望获得的情感满足",
        "category": "情感需求",
        "merge_strategy": "llm_judge",
        "examples": ["被认可", "陪伴", "被理解", "安全感", "自由"]
    },
    "security_source": {
        "description": "安全感来源",
        "definition": "什么让用户感到安心",
        "category": "情感需求",
        "merge_strategy": "llm_judge",
        "examples": ["被认可", "有人陪伴", "经济稳定", "计划明确"]
    },
    "anxiety_trigger": {
        "description": "焦虑触发器",
        "definition": "什么容易让用户焦虑",
        "category": "情感需求",
        "merge_strategy": "append",
        "examples": ["被催婚", "工作deadline", "社交场合", "被否定"]
    },
    "disliked_responses": {
        "description": "讨厌的回应",
        "definition": "用户反感的沟通方式",
        "category": "情感需求",
        "merge_strategy": "append",
        "examples": ["说教", "敷衍", "过度乐观", "讲大道理"]
    },
    "liked_responses": {
        "description": "喜欢的回应",
        "definition": "用户偏好的沟通方式",
        "category": "情感需求",
        "merge_strategy": "append",
        "examples": ["倾听", "共情", "直接建议", "幽默化解"]
    },
    "boundaries": {
        "description": "边界",
        "definition": "用户不愿讨论的话题",
        "category": "情感需求",
        "merge_strategy": "append",
        "examples": ["不聊家庭", "不催婚", "不提前任"]
    },
    
    # ==================== 沟通偏好 (3) ====================
    "reply_style_pref": {
        "description": "回复风格偏好",
        "definition": "用户喜欢的回复语气",
        "category": "沟通偏好",
        "merge_strategy": "replace",
        "examples": ["简洁", "温柔", "幽默", "理性"]
    },
    "role_expectation": {
        "description": "角色期望",
        "definition": "用户希望AI扮演的角色",
        "category": "沟通偏好",
        "merge_strategy": "replace",
        "examples": ["朋友", "知心姐姐", "理性分析师", "树洞"]
    },
    "interaction_mode": {
        "description": "互动模式",
        "definition": "用户偏好的互动方式",
        "category": "沟通偏好",
        "merge_strategy": "replace",
        "examples": ["主动关心", "被动回应", "深度对话", "轻松闲聊"]
    },
    
    # ==================== 深层心理 (4) ====================
    "core_beliefs": {
        "description": "核心信念",
        "definition": "用户对自己/世界的基本看法",
        "category": "深层心理",
        "merge_strategy": "llm_judge",
        "examples": ["努力就会成功", "人不可信", "我不够好", "世界是公平的"]
    },
    "values": {
        "description": "价值观",
        "definition": "用户认为重要的原则",
        "category": "深层心理",
        "merge_strategy": "append",
        "examples": ["重视家庭", "追求自由", "讨厌虚伪", "崇尚效率"]
    },
    "defense_mechanisms": {
        "description": "心理防御机制",
        "definition": "用户应对焦虑的潜意识策略",
        "category": "深层心理",
        "merge_strategy": "llm_judge",
        "examples": ["合理化", "投射", "否认", "压抑"]
    },
    "attachment_style": {
        "description": "依恋风格",
        "definition": "用户在亲密关系中的模式",
        "category": "深层心理",
        "merge_strategy": "replace",
        "examples": ["安全型", "焦虑型", "回避型", "混乱型"]
    },
    "emotion_regulation": {
        "description": "情绪调节方式",
        "definition": "用户习惯的自我调节方法",
        "category": "深层心理",
        "merge_strategy": "llm_judge",
        "examples": ["独处冷静", "找人倾诉", "运动发泄", "写日记"]
    },
}


# ============================================================================
# 合并后的完整槽位表（向后兼容）
# ============================================================================
SLOT_SCHEMA: Dict[str, Dict] = {**EXTRACTION_SLOTS, **PSYCHOLOGIST_SLOTS}


def get_slots_by_category() -> Dict[str, List[str]]:
    """按类别分组槽位"""
    categories: Dict[str, List[str]] = {}
    for slot_key, slot_info in SLOT_SCHEMA.items():
        category = slot_info["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append(slot_key)
    return categories


def get_slot_keys() -> List[str]:
    """获取所有槽位 key"""
    return list(SLOT_SCHEMA.keys())


def get_extraction_slot_keys() -> List[str]:
    """获取 ExtractionAgent 负责的槽位 key"""
    return list(EXTRACTION_SLOTS.keys())


def get_psychologist_slot_keys() -> List[str]:
    """获取 PsychologistAgent 负责的槽位 key"""
    return list(PSYCHOLOGIST_SLOTS.keys())


def get_extraction_prompt() -> str:
    """生成用于 LLM 抽取槽位的 prompt（ExtractionAgent 用）"""
    slot_descriptions = []
    for key, info in EXTRACTION_SLOTS.items():
        examples = "、".join(info["examples"][:3])
        slot_descriptions.append(f'  - {key}: {info["description"]}（如：{examples}）')
    
    return f"""你是一个用户画像分析助手。根据对话内容，提取用户的个人信息填入对应槽位。

可用槽位：
{chr(10).join(slot_descriptions)}

规则：
1. 只提取对话中明确提到的信息，不要推测
2. 如果某个槽位没有相关信息，不要包含在输出中
3. 对于列表类型的槽位（如 hobbies），返回数组

请输出 JSON 格式，只包含有值的槽位：
{{"nickname": "值", "occupation": "值", ...}}

如果没有任何可提取的信息，返回空对象 {{}}"""


def get_merge_judgment_prompt(slot_key: str, old_value: str, new_value: str) -> str:
    """生成用于 LLM 判断合并策略的 prompt"""
    slot_info = SLOT_SCHEMA.get(slot_key, {})
    return f"""你是一个用户画像更新助手。

槽位：{slot_key}（{slot_info.get('description', '')}）
旧值：{old_value}
新值：{new_value}

请判断如何处理：
1. 如果新值是对旧值的更新/修正，返回 {{"action": "replace", "value": "新值"}}
2. 如果新值是对旧值的补充，返回 {{"action": "merge", "value": "合并后的值"}}
3. 如果新值与旧值矛盾，以新值为准，返回 {{"action": "replace", "value": "新值"}}

只返回 JSON，不要其他内容。"""

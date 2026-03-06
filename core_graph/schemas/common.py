from pydantic import BaseModel, Field

class MessageItem(BaseModel):
    """对话消息模型 - 通用"""
    role: str = Field(..., description="角色: user 或 assistant")
    content: str = Field(..., description="消息内容")

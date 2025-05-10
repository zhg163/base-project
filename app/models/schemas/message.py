from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class MessageBase(BaseModel):
    """消息基础模型"""
    role: str = Field(..., description="消息角色：user, assistant, system")
    content: str = Field(..., description="消息内容")
    
class Message(MessageBase):
    """完整消息模型"""
    timestamp: str = Field(..., description="消息时间戳")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")

class MessageCreate(MessageBase):
    """创建消息模型"""
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")

class MessageResponse(Message):
    """响应消息模型"""
    pass 
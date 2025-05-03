from datetime import datetime
from typing import Dict, List, Optional, Set, Any
from pydantic import Field

from app.models.entities.base import BaseModel

class ChatMessage(BaseModel):
    """聊天消息模型"""
    
    _redis_key_prefix = "chat:message"
    
    conversation_id: str
    role: str  # 'user', 'assistant', 'system'
    content: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @classmethod
    def get_conversation_key(cls, conversation_id: str) -> str:
        """获取会话消息列表的键名
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            会话消息列表的键名
        """
        return f"chat:conversation:{conversation_id}:messages"

class ChatConversation(BaseModel):
    """聊天会话模型"""
    
    _redis_key_prefix = "chat:conversation"
    
    title: Optional[str] = None
    user_id: str
    model_id: str = "deepseek"  # 默认使用deepseek模型
    message_count: int = 0
    last_message_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class UserProfile(BaseModel):
    """用户资料模型"""
    
    _redis_key_prefix = "user:profile"
    
    username: str
    email: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False
    preferences: Dict[str, Any] = Field(default_factory=dict)
    conversation_ids: List[str] = Field(default_factory=list)

class AIModel(BaseModel):
    """AI模型信息模型"""
    
    _redis_key_prefix = "ai:model"
    
    name: str
    provider: str  # 'openai', 'deepseek', 'qwen'等
    api_base: Optional[str] = None
    default_parameters: Dict[str, Any] = Field(default_factory=dict)
    is_available: bool = True
    max_tokens: int = 4096
    supports_streaming: bool = True 
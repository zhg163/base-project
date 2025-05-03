from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import Field

from app.models.entities.mongo_base import MongoModel

class User(MongoModel):
    """用户模型"""
    
    _collection_name = "users"
    
    name: str = Field(..., description="用户名称")
    username: str = Field(..., description="用户登录名")
    email: Optional[str] = Field(None, description="用户邮箱")
    avatar: Optional[str] = Field(None, description="用户头像")
    description: Optional[str] = Field(None, description="用户描述")
    tags: Optional[List[str]] = Field(default_factory=list, description="用户标签")
    is_active: Optional[bool] = Field(True, description="是否激活")
    hashed_password: Optional[str] = Field(None, description="密码哈希")
    is_admin: bool = False
    last_login: Optional[datetime] = None
    profile: Dict[str, Any] = Field(default_factory=dict)

class Document(MongoModel):
    """文档模型"""
    
    _collection_name = "documents"
    
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)
    owner_id: str
    is_public: bool = False
    view_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class EmbeddingRecord(MongoModel):
    """嵌入记录模型"""
    
    _collection_name = "embeddings"
    
    text: str
    embedding: List[float]
    document_id: Optional[str] = None
    chunk_index: Optional[int] = None
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict) 
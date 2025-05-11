from typing import Dict, List, Optional, Any
from pydantic import Field, BaseModel
from app.models.entities.mongo_base import MongoModel
from datetime import datetime


class Role(MongoModel):
    """角色数据模型"""
    
    _collection_name = "roles"
    
    name: str = Field(..., description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    personality: Optional[str] = Field(None, description="角色性格")
    speech_style: Optional[str] = Field(None, description="角色语言风格")
    keywords: Optional[List[str]] = Field(default_factory=list, description="角色关键词")
    temperature: Optional[float] = Field(0.7, description="生成温度")
    prompt_templates: Optional[List[str]] = Field(default_factory=list, description="提示词模板")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    is_active: Optional[bool] = Field(True, description="是否激活")
    # 新增字段
    faction: Optional[str] = Field(None, description="角色阵营")
    job: Optional[str] = Field(None, description="角色职业类别")
    


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

class Role(MongoModel):
    """角色数据模型"""
    
    _collection_name = "roles"
    
    name: str = Field(..., description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    personality: Optional[str] = Field(None, description="角色性格")
    speech_style: Optional[str] = Field(None, description="角色语言风格")
    keywords: Optional[List[str]] = Field(default_factory=list, description="角色关键词")
    temperature: Optional[float] = Field(0.7, description="生成温度")
    prompt_templates: Optional[List[str]] = Field(default_factory=list, description="提示词模板")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    is_active: Optional[bool] = Field(True, description="是否激活")

class RoleReference(MongoModel):
    """角色引用数据模型"""
    _collection_name = "role_references"
    
    role_id: str = Field(..., description="角色ID")
    role_name: str = Field(..., description="角色名称")
    system_prompt: Optional[str] = None

class Session(MongoModel):
    """用户会话数据模型"""
    
    _collection_name = "sessions"
    
    class_id: str = Field(..., description="聊天室ID")
    class_name: str = Field(..., description="聊天室名称")
    user_id: str = Field(..., description="用户ID")
    user_name: str = Field(..., description="用户名称")
    roles: List[RoleReference] = Field(default_factory=list, description="角色列表")
    session_id: str = Field(..., description="会话ID", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    is_active: bool = Field(True, description="是否激活")

    class Config:
        # 定义session_id的唯一索引
        indexes = [
            {"fields": ["session_id"], "unique": True}
        ]
        collection_name = "sessions" 
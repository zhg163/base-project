from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class RoleInfoSchema(BaseModel):
    """角色信息模型"""
    role_id: str
    role_name: str

class SessionBase(BaseModel):
    """会话基础数据模型"""
    class_id: Optional[str] = Field(None, description="聊天室ID")
    class_name: str = Field(..., description="聊天室名称")
    user_id: str = Field(..., description="用户ID")
    user_name: str = Field(..., description="用户名称")
    roles: List[RoleInfoSchema] = Field(..., description="角色列表")

class SessionCreate(SessionBase):
    """创建会话的数据模型"""
    pass

class SessionUpdate(BaseModel):
    """更新会话的数据模型"""
    class_name: Optional[str] = None
    roles: Optional[List[RoleInfoSchema]] = None
    is_active: Optional[bool] = None

class SessionResponse(SessionBase):
    """会话响应数据模型"""
    id: str
    session_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: bool

    class Config:
        from_attributes = True 
from typing import List, Optional
from pydantic import BaseModel, Field

class UserBase(BaseModel):
    """用户基础模型"""
    name: str = Field(..., description="用户名称")
    username: str = Field(..., description="用户登录名")
    email: Optional[str] = Field(None, description="用户邮箱")
    avatar: Optional[str] = Field(None, description="用户头像")
    description: Optional[str] = Field(None, description="用户描述")
    tags: Optional[List[str]] = Field(default_factory=list, description="用户标签")
    is_active: Optional[bool] = Field(True, description="是否激活")

class UserCreate(UserBase):
    """创建用户请求模型"""
    pass

class UserUpdate(BaseModel):
    """更新用户请求模型(所有字段可选)"""
    name: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    """用户响应模型"""
    id: str

    class Config:
        orm_mode = True 
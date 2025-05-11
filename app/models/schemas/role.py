from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class RoleBase(BaseModel):
    """角色基础数据模型"""
    name: str = Field(..., description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    personality: Optional[str] = Field(None, description="角色性格")
    speech_style: Optional[str] = Field(None, description="角色语言风格")
    keywords: Optional[List[str]] = Field(None, description="角色关键词")
    temperature: Optional[float] = Field(None, description="生成温度")
    prompt_templates: Optional[List[str]] = Field(None, description="提示词模板")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    faction: Optional[str] = Field(None, description="角色阵营")
    job: Optional[str] = Field(None, description="角色职业类别")
    is_active: Optional[bool] = Field(None, description="是否激活")

class RoleCreate(RoleBase):
    """创建角色的数据模型"""
    pass

class RoleUpdate(RoleBase):
    """更新角色的数据模型"""
    name: Optional[str] = Field(None, description="角色名称")

class RoleResponse(RoleBase):
    """角色响应数据模型"""
    id: str

    class Config:
        from_attributes = True 
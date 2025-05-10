# app/services/ai/prompt/role_prompt_service.py
from typing import Optional, Dict, Any, List
import json
from app.services.storage.redis_service import RedisService
from app.core.config import settings 
from app.models.schemas.role import RoleResponse, RoleCreate, RoleUpdate
from app.services.storage.mongo_repository import MongoRepository
from app.utils.logging import logger

class RolePromptService:
    """角色提示词管理服务"""
    
    def __init__(self, redis_client: RedisService.Redis = None, role_repo: MongoRepository = None):
        self.redis = redis_client 
        self.role_repo = role_repo
    
    async def create_role(self, role_data: RoleCreate) -> Optional[RoleResponse]:
        """创建新角色提示词"""
        if not self.role_repo:
            logger.error("缺少角色仓储，无法创建角色")
            return None
            
        # 创建角色
        role = await self.role_repo.create(role_data.dict())
        if not role:
            return None
            
        # 缓存到Redis
        role_dict = role.dict()
        await self.redis.set(
            f"role:{role.id}", 
            json.dumps(role_dict),
            ex=3600  # 缓存1小时
        )
        
        return RoleResponse(**role_dict)
    
    async def update_role(self, role_id: str, role_data: RoleUpdate) -> Optional[RoleResponse]:
        """更新角色提示词"""
        if not self.role_repo:
            logger.error("缺少角色仓储，无法更新角色")
            return None
            
        # 更新角色
        role = await self.role_repo.update(role_id, role_data.dict(exclude_unset=True))
        if not role:
            return None
            
        # 更新Redis缓存
        role_dict = role.dict()
        await self.redis.set(
            f"role:{role.id}", 
            json.dumps(role_dict),
            ex=3600  # 缓存1小时
        )
        
        return RoleResponse(**role_dict)
    
    async def delete_role(self, role_id: str) -> bool:
        """删除角色提示词"""
        if not self.role_repo:
            return False
            
        # 删除角色
        result = await self.role_repo.delete(role_id)
        
        # 删除Redis缓存
        await self.redis.delete(f"role:{role_id}")
        
        return result
    
    async def get_all_roles(self) -> List[RoleResponse]:
        """获取所有角色提示词"""
        if not self.role_repo:
            return []
            
        roles = await self.role_repo.find_many({})
        return [RoleResponse(**role.dict()) for role in roles]
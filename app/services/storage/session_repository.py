from typing import Optional, List, Dict, Any
from app.services.storage.mongo_repository import MongoRepository
from app.models.entities.mongo_models import Session
from app.utils.logging import logger

class SessionRepository(MongoRepository):
    """会话仓库，处理Session实体的存取"""
    
    def __init__(self, model_class=Session, mongo_service=None):
        super().__init__(model_class, mongo_service)
        # 其他初始化...
    
    async def find_by_session_id(self, session_id: str) -> Optional[Session]:
        """通过session_id字段查询会话"""
        return await self.find_one({"session_id": session_id})
        
    async def find_by_user_id(self, user_id: str, skip: int = 0, limit: int = 100) -> List[Session]:
        """查询用户的所有会话"""
        return await self.find_many(
            filter_dict={"user_id": user_id},
            skip=skip,
            limit=limit
        )
        
    async def find_active_sessions(self, skip: int = 0, limit: int = 100) -> List[Session]:
        """查询所有激活状态的会话"""
        return await self.find_many(
            filter_dict={"is_active": True},
            skip=skip,
            limit=limit
        ) 
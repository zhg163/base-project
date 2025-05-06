import uuid
import hashlib
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

from app.models.entities.mongo_models import Session, RoleReference, Role
from app.services.storage.session_repository import SessionRepository
from app.services.storage.mongo_repository import MongoRepository
from app.services.storage.redis_service import RedisService
from app.utils.logging import logger

class SessionService:
    """会话服务，处理会话业务逻辑"""
    
    def __init__(self, session_repository: SessionRepository, redis_service=None, mongo_repository=None):
        self.session_repository = session_repository
        self.redis_service = redis_service
        self.mongo_repository = mongo_repository
    
    async def create_session(self, class_name: str, user_id: str, user_name: str, roles: List[dict], class_id: Optional[str] = None) -> Session:
        """创建新会话，生成会话ID"""
        # 获取当前时间戳
        timestamp = str(datetime.now().timestamp())
        
        # 构建角色信息列表，并获取system_prompt
        roles_data = []
        for role in roles:
            role_reference = RoleReference(
                role_id=role["role_id"], 
                role_name=role["role_name"]
            )
            
            # 直接从角色表中查询，使用通用仓库方法
            if self.mongo_repository:
                try:
                    logger.debug(f"Fetching role data for role_id: {role['role_id']}")
                    role_doc = await self.mongo_repository.find_one({"_id": ObjectId(role["role_id"])})
                    if role_doc:
                        logger.debug(f"Role found: {role_doc.name}")
                        if role_doc.system_prompt:
                            role_reference.system_prompt = role_doc.system_prompt
                            logger.debug(f"Assigned system_prompt: {role_doc.system_prompt[:20]}...")
                        else:
                            logger.warning(f"Role {role_doc.name} has no system_prompt")
                    else:
                        logger.warning(f"No role found with id: {role['role_id']}")
                except Exception as e:
                    logger.error(f"Error fetching role data for {role['role_id']}: {e}", exc_info=True)
            
            roles_data.append(role_reference)
        
        # 连接所有角色名称
        role_names = "".join([role["role_name"] for role in roles])
        
        # 生成 session_id
        session_id = self.generate_session_id(class_name, user_name, role_names, timestamp)
        
        # 如果前端未提供class_id，则生成一个
        if not class_id:
            class_id = str(uuid.uuid4())
        
        # 创建会话实例
        session = Session(
            class_id=class_id,
            class_name=class_name,
            user_id=user_id,
            user_name=user_name,
            roles=roles_data,
            session_id=session_id
        )
        
        # 保存到数据库
        created_session = await self.session_repository.create(session)
        logger.info(f"Created new session with ID: {session_id}, class_id: {class_id}")
        
        # 同步到Redis
        if self.redis_service:
            await self.redis_service.set_session(
                session_id=session_id,
                session_data=created_session.model_dump()
            )
        
        return created_session
    
    def generate_session_id(self, class_name: str, user_name: str, role_names: str, timestamp: str) -> str:
        """生成会话ID: MD5(class_name + user_name + role_names + timestamp)"""
        # 将所有参数转换为字符串并拼接
        combined_string = f"{class_name}{user_name}{role_names}{timestamp}"
        
        # 计算MD5哈希值
        md5_hash = hashlib.md5(combined_string.encode()).hexdigest()
        
        return md5_hash 

    async def get_session_by_id(self, session_id: str) -> Optional[Session]:
        """根据session_id获取会话"""
        session = await self.session_repository.find_one({"session_id": session_id})
        
        # 添加日志 - 检查数据库返回内容
        if session:
            logger.info(f"Retrieved session from DB: {session_id}")
            if session.roles:
                for i, role in enumerate(session.roles):
                    logger.info(f"Role {i} in session: id={role.role_id}, name={role.role_name}")
                    # 检查system_prompt是否存在
                    if hasattr(role, 'system_prompt'):
                        logger.info(f"Role {i} has system_prompt: {role.system_prompt and 'Yes' or 'None'}")
                    else:
                        logger.warning(f"Role {i} has no system_prompt attribute")
        else:
            logger.warning(f"No session found with id: {session_id}")
        
        return session

    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        # 先获取会话，确保存在
        session = await self.get_session_by_id(session_id)
        if not session:
            return False
        
        # 使用_id进行删除
        result = await self.session_repository.delete(str(session.id))
        
        # 从Redis删除
        if self.redis_service and result:
            await self.redis_service.delete_session(session_id)
            
        return result 
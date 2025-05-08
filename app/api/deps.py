from fastapi import Depends
from app.services.storage.mongo_repository import MongoRepository
from app.services.storage.session_repository import SessionRepository
from app.services.storage.redis_service import RedisService
from app.services.storage.mongo_service import get_mongo_service
from app.services.ai.memory.memory_service import MemoryService

def get_user_repository():
    """获取用户仓库实例"""
    from app.services.storage.mongo_service import MongoService
    from app.models.entities.mongo_models import User
    from app.core.config import settings
    from app.utils.logging import logger
    
    logger.debug(f"Creating MongoDB service with URI: {settings.MONGODB_URL[:10]}... and DB: {settings.MONGODB_DB_NAME}")
    
    # 确保使用完整的认证连接字符串
    mongo_service = MongoService(
        uri=settings.MONGODB_URL,
        db_name=settings.MONGODB_DB_NAME
    )
    
    logger.debug(f"Creating User repository")
    return MongoRepository(User, mongo_service=mongo_service)

def get_session_repository(mongo_service=Depends(get_mongo_service)):
    """获取会话存储库实例"""
    from app.models.entities.mongo_models import Session
    from app.core.config import settings
    from app.utils.logging import logger
    
    logger.debug(f"Creating SessionRepository")
    
    return SessionRepository(model_class=Session, mongo_service=mongo_service)

async def get_redis_service():
    """获取Redis服务实例"""
    from app.services.storage.redis_service import RedisService
    from app.core.config import settings
    
    redis_service = RedisService(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        db=settings.REDIS_DB
    )
    return redis_service

def get_mongo_repository_factory():
    """获取MongoDB仓库工厂函数"""
    from app.services.storage.mongo_service import MongoService
    from app.services.storage.mongo_repository import MongoRepository
    from app.core.config import settings
    
    # 创建共享的MongoDB服务实例
    mongo_service = MongoService(
        uri=settings.MONGODB_URL,
        db_name=settings.MONGODB_DB_NAME
    )
    
    # 返回一个工厂函数，可以为任何模型创建仓库
    def create_repository(model_class):
        return MongoRepository(model_class, mongo_service=mongo_service)
    
    return create_repository

def get_role_repository():
    """获取角色仓库实例 - 使用通用MongoDB仓库"""
    from app.services.storage.mongo_service import MongoService
    from app.models.entities.mongo_models import Role
    from app.core.config import settings
    
    mongo_service = MongoService(
        uri=settings.MONGODB_URL,
        db_name=settings.MONGODB_DB_NAME
    )
    
    # 使用通用仓库，传入Role模型
    return MongoRepository(Role, mongo_service=mongo_service)

def get_session_service(
    session_repository: SessionRepository = Depends(get_session_repository),
    redis_service: RedisService = Depends(get_redis_service),
    role_repository = Depends(get_role_repository)
):
    """获取会话服务实例"""
    from app.services.session_service import SessionService
    
    return SessionService(
        session_repository=session_repository,
        redis_service=redis_service,
        mongo_repository=role_repository
    )

def get_llm_service():
    """获取LLM服务实例"""
    from app.services.ai.llm.llm_factory import LLMFactory
    from app.core.config import settings
    import os
    
    # 从环境变量获取，如果不存在则使用默认值
    model_type = os.getenv("DEFAULT_MODEL_TYPE", "deepseek")
    
    factory = LLMFactory()
    return factory.get_llm_service(model_type)

def get_role_selector():
    """获取角色选择器实例"""
    from app.services.ai.llm.role_selector import RoleSelector
    
    # 暂时使用None作为LLM服务，实际运行时会通过依赖注入提供
    # 角色选择器会在ChatService中重新赋值正确的LLM服务
    return RoleSelector(llm_service=None)

def get_chat_service(
    session_service = Depends(get_session_service),
    llm_service = Depends(get_llm_service),
    role_selector = Depends(get_role_selector)
):
    """获取聊天服务实例"""
    from app.services.chat_service import ChatService
    
    # 确保角色选择器使用正确的LLM服务
    role_selector.llm_service = llm_service
    
    return ChatService(
        llm_service=llm_service,
        session_service=session_service,
        role_selector=role_selector
    )

def get_memory_service():
    """获取记忆服务实例"""
    return MemoryService()
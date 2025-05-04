def get_user_repository():
    """获取用户仓库实例"""
    from app.services.storage.mongo_service import MongoService
    from app.services.storage.mongo_repository import MongoRepository
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

def get_role_repository():
    """获取角色仓库实例"""
    from app.services.storage.mongo_service import MongoService
    from app.services.storage.mongo_repository import MongoRepository
    from app.models.entities.mongo_models import Role
    from app.core.config import settings
    from app.utils.logging import logger
    
    logger.debug(f"Creating RoleRepository")
    
    mongo_service = MongoService(
        uri=settings.MONGODB_URL,
        db_name=settings.MONGODB_DB_NAME
    )
    
    return MongoRepository(Role, mongo_service=mongo_service)

def get_session_repository():
    """获取会话存储库实例"""
    from app.services.storage.mongo_service import MongoService
    from app.services.storage.session_repository import SessionRepository
    from app.models.entities.mongo_models import Session
    from app.core.config import settings
    from app.utils.logging import logger
    
    logger.debug(f"Creating SessionRepository")
    
    mongo_service = MongoService(
        uri=settings.MONGODB_URL,
        db_name=settings.MONGODB_DB_NAME
    )
    
    return SessionRepository(Session, mongo_service=mongo_service)

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

async def get_session_service():
    """获取会话服务实例（异步）"""
    from app.services.session_service import SessionService
    
    # 获取依赖的服务
    session_repository = get_session_repository()  # 同步函数可直接调用
    redis_service = await get_redis_service()      # 异步函数必须await
    
    # 创建并返回会话服务
    return SessionService(
        session_repository=session_repository,
        redis_service=redis_service
    )

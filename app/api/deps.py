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

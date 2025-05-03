from typing import Callable
from fastapi import FastAPI
from app.core.config import settings
from app.utils.logging import get_logger

logger = get_logger("app")

def startup_event_handler(app: FastAPI) -> Callable:
    """应用启动事件处理器"""
    
    async def start_app() -> None:
        # 记录应用启动
        logger.info(
            f"Starting application {settings.PROJECT_NAME} v{settings.VERSION}",
            extra={
                "data": {
                    "host": settings.HOST,
                    "port": settings.PORT,
                    "debug_mode": settings.DEBUG_MODE,
                    "environment": "development" if settings.DEBUG_MODE else "production",
                }
            }
        )
        
        # 添加数据库连接日志
        logger.info("Initializing database connections...")
        
        try:
            # 测试 MongoDB 连接
            from app.services.storage.mongo_service import MongoService
            
            mongo_service = MongoService(
                uri=settings.MONGODB_URL,
                db_name=settings.MONGODB_DB_NAME
            )
            # 获取客户端会触发连接
            client = mongo_service.client
            db = mongo_service.db
            # 测试数据库连接
            collections = db.list_collection_names()
            logger.info(f"MongoDB connected, available collections: {collections}")
        except Exception as e:
            logger.error(f"Failed to initialize MongoDB: {str(e)}")
        
        # 可以添加其他数据库连接测试（Redis等）
        
        logger.info("Application startup complete")
    
    return start_app


def shutdown_event_handler(app: FastAPI) -> Callable:
    """应用关闭事件处理器"""
    
    async def stop_app() -> None:
        # 记录应用关闭
        logger.info(f"Shutting down application {settings.PROJECT_NAME}")
        
        # 其他关闭逻辑
        # ...
        
        logger.info("Application shutdown complete")
    
    return stop_app

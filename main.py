#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI项目入口文件
"""

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.router import api_router
from app.core.config import settings
from app.core.events import startup_event_handler, shutdown_event_handler
from app.api.middleware.logging import RequestLoggingMiddleware
from app.utils.logging import get_logger

# 初始化应用日志
logger = get_logger("main")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False
)

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 添加日志中间件
app.add_middleware(RequestLoggingMiddleware)

# 注册路由
app.include_router(api_router, prefix=settings.API_PREFIX)

# 注册事件处理器
app.add_event_handler("startup", startup_event_handler(app))
app.add_event_handler("shutdown", shutdown_event_handler(app))

# 记录应用初始化
logger.info(f"Application {settings.PROJECT_NAME} initialized")

if __name__ == "__main__":
    logger.info(f"Starting uvicorn server at {settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG_MODE,
        log_level=settings.LOG_LEVEL.lower(),
    )
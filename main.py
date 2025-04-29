#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI项目入口文件
"""

import uvicorn
from fastapi import FastAPI
from app.api.router import api_router
from app.core.config import settings
from app.core.events import startup_event_handler, shutdown_event_handler

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 注册路由
app.include_router(api_router, prefix=settings.API_PREFIX)

# 注册事件处理器
app.add_event_handler("startup", startup_event_handler(app))
app.add_event_handler("shutdown", shutdown_event_handler(app))

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG_MODE,
        log_level="info",
    )
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置管理模块
"""

import os
from typing import Any, Dict, List, Optional
from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    """应用配置类"""
    
    # 基本配置
    PROJECT_NAME: str = "AI项目"
    PROJECT_DESCRIPTION: str = "基于FastAPI的AI应用"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"
    DEBUG_MODE: bool = True
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # 安全配置
    SECRET_KEY: str = "your-secret-key-here"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # 数据库配置
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "ai_project"
    
    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # MinIO配置
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    
    # AI模型配置
    LLM_MODEL: str = "gpt-3.5-turbo"
    EMBEDDING_MODEL: str = "text-embedding-ada-002"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建全局设置对象
settings = Settings()
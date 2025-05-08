#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置管理模块
"""

import os
from typing import Any, Dict, List, Optional

# 修改导入语句 - 使用新的导入路径
from pydantic import field_validator  # 替代旧的 validator
from pydantic_settings import BaseSettings  # 从新包导入


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
    PORT: int = 8001
    
    # 安全配置 - 只保留默认值，实际值从环境变量加载
    SECRET_KEY: str = "your-secret-key-here"  # 添加默认值避免启动错误
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # 数据库配置 - 连接URL从环境变量加载
    MONGODB_URL: str = "mongodb://localhost:27017"  # 添加默认值
    MONGODB_DB_NAME: str = "ai_project"
    
    # Redis配置 - 主机和端口保留，密码从环境变量加载
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # MinIO配置 - 主机信息保留，凭证从环境变量加载
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"  # 添加默认值
    MINIO_SECRET_KEY: str = "minioadmin"  # 添加默认值
    MINIO_SECURE: bool = False
    
    # AI模型配置 - 修改默认模型为 deepseek
    DEFAULT_LLM_MODEL: str = "deepseek"  # 修改默认模型
    
    # DeepSeek 配置
    DEEPSEEK_API_BASE: str = "https://api.deepseek.com/v1"
    DEEPSEEK_API_KEY: str = "your_deepseek_api_key_here"
    
    # OpenAI 配置（设为可选）
    LLM_MODEL: str = "gpt-3.5-turbo"  # 保留旧的配置名称兼容性
    OPENAI_API_KEY: Optional[str] = None  # 设为可选
    EMBEDDING_MODEL: str = "text-embedding-ada-002"  # 仍使用OpenAI嵌入模型
    
    # Qwen 配置
    QWEN_API_BASE: str = "https://api.qianwen-api.com/v1"
    QWEN_API_KEY: str = "your_qwen_api_key_here"
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(levelname)s %(message)s [time=%(asctime)s, module=%(module)s, func=%(funcName)s, line=%(lineno)d]"
    LOG_FILE: Optional[str] = None
    JSON_LOGS: bool = True
    LOG_REQUEST_BODY: bool = False
    LOG_RESPONSE_BODY: bool = False
    LOG_PERFORMANCE: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 允许额外的环境变量

    @field_validator("SECRET_KEY", "DEEPSEEK_API_KEY", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY")
    @classmethod
    def validate_required_keys(cls, v, info):
        # 验证必须存在的密钥
        default_values = {
            "SECRET_KEY": "your-secret-key-here",
            "DEEPSEEK_API_KEY": "your_deepseek_api_key_here",
            "MINIO_ACCESS_KEY": "minioadmin",
            "MINIO_SECRET_KEY": "minioadmin"
        }
        
        field_name = info.field_name
        if v != default_values.get(field_name) and (not v or len(v) < 8):
            raise ValueError(f"{field_name} must be provided and sufficiently complex")
        return v
    
    @field_validator("OPENAI_API_KEY", "QWEN_API_KEY")
    @classmethod
    def validate_optional_keys(cls, v, info):
        # 验证可选密钥 - 只在有值时检查
        if v is not None and v != "" and v != f"your_{info.field_name.lower()}" and len(v) < 8:
            raise ValueError(f"If provided, {info.field_name} must be sufficiently complex")
        return v

    @property
    def redis_connection_string(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def is_openai_available(self) -> bool:
        """检查OpenAI配置是否可用"""
        return self.OPENAI_API_KEY is not None and self.OPENAI_API_KEY != "your-openai-api-key"


# 创建全局设置对象
settings = Settings()

# 在配置设置中修改
LOGGING = {
    "version": 1,
    "formatters": {
        "standard": {
            "format": "%(levelname)s %(message)s [time=%(asctime)s, module=%(module)s, func=%(funcName)s, line=%(lineno)d]",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    }
    # ...其他配置保持不变
}
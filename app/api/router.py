#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API路由管理
"""

from fastapi import APIRouter
from app.api.endpoints import users, roles, sessions, chat  # 添加sessions导入

# 创建主路由
api_router = APIRouter()

# 导入并包含各个端点路由
# from app.api.endpoints import users, chat, documents

# 注册用户相关路由
api_router.include_router(users.router, prefix="/users", tags=["用户"])
# 注册角色相关路由
api_router.include_router(roles.router, prefix="/roles", tags=["角色"])
# 注册会话相关路由
api_router.include_router(sessions.router, prefix="/custom-sessions", tags=["会话"])

# 如注册聊天路由
api_router.include_router(chat.router, prefix="/llm", tags=["LLM"])

# api_router.include_router(chat.router, prefix="/chat", tags=["聊天"])
# api_router.include_router(documents.router, prefix="/documents", tags=["文档"])
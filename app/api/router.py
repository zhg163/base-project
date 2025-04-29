#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API路由管理
"""

from fastapi import APIRouter

# 创建主路由
api_router = APIRouter()

# 导入并包含各个端点路由
# from app.api.endpoints import users, chat, documents

# api_router.include_router(users.router, prefix="/users", tags=["用户"])
# api_router.include_router(chat.router, prefix="/chat", tags=["聊天"])
# api_router.include_router(documents.router, prefix="/documents", tags=["文档"])
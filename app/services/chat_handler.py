# 或者任何处理聊天的控制器中

import logging
from typing import Dict, Any, Optional, AsyncGenerator
from fastapi import HTTPException

from app.services.chat_service import ChatService
from app.services.ai.memory.memory_service import MemoryService

logger = logging.getLogger(__name__)

class ChatHandler:
    """聊天请求处理器，负责处理和路由聊天相关请求"""
    
    def __init__(self, chat_service: ChatService = None, memory_service: MemoryService = None):
        """初始化聊天处理器"""
        self.chat_service = chat_service or ChatService()
        self.memory_service = memory_service or MemoryService()
        logger.info("聊天处理器初始化完成")
    
    async def handle_chat_request(self, request_data):
        """处理聊天请求"""
        session_id = request_data.get("session_id")
        message = request_data.get("message")
        user_id = request_data.get("user_id", "anonymous")
        user_name = request_data.get("user_name")
        
        logger.info(f"处理聊天请求: session_id={session_id}, user_id={user_id}")
        
        # 获取历史消息
        message_history = await self.memory_service.build_message_history(session_id)
        
        # 检查历史消息的有效性
        if not message_history:
            logger.warning(f"未获取到历史消息，可能是新会话或记忆服务出错: session_id={session_id}")
        else:
            logger.info(f"消息历史获取成功: 条数={len(message_history)}")
            # 分析历史消息的时间分布
            timestamps = [msg.get("timestamp", "unknown") for msg in message_history if isinstance(msg, dict)]
            logger.info(f"消息时间分布: {timestamps[-5:] if len(timestamps) > 5 else timestamps}")
        
        # 调用聊天服务
        try:
            # 标准聊天响应处理
            response = await self.chat_service.chat(
                session_id=session_id,
                message=message,
                user_id=user_id
            )
            logger.info(f"聊天响应生成成功: session_id={session_id}, 响应长度={len(response.get('content', ''))}")
            return response
        except Exception as e:
            logger.error(f"处理聊天请求失败: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"聊天处理错误: {str(e)}")
    
    async def handle_stream_chat_request(self, request_data):
        """处理流式聊天请求"""
        session_id = request_data.get("session_id")
        message = request_data.get("message")
        user_id = request_data.get("user_id", "anonymous")
        user_name = request_data.get("user_name")
        role_id = request_data.get("role_id")
        role_name = request_data.get("role_name", "assistant")
        
        logger.info(f"处理流式聊天请求: session_id={session_id}, user_id={user_id}")
        
        try:
            # 保存用户消息到记忆服务
            await self.memory_service.add_user_message(
                session_id=session_id,
                message=message,
                user_id=user_id,
                user_name=user_name
            )
            
            # 获取流式响应
            response_stream = self.chat_service.stream_response(
                session_id=session_id,
                user_message=message,
                role_id=role_id,
                role_name=role_name
            )
            
            # 直接返回流对象，由FastAPI路由处理成SSE流
            return response_stream
        except Exception as e:
            logger.error(f"处理流式聊天请求失败: {str(e)}", exc_info=True)
            # 对于流式响应的错误，我们需要返回一个生成器而不是抛出异常
            async def error_generator():
                yield {"error": str(e)}
            
            return error_generator() 
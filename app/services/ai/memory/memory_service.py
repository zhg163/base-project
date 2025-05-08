"""记忆服务，负责管理会话历史与构建对话上下文"""

import os
import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import json
import uuid

from .redis_memory import RedisMemory
from .mongo_backup import MongoBackup
from app.utils.logging import logger, AILogger, LogContext

logger = logging.getLogger(__name__)

# 基础消息结构 - 所有消息共享
base_message = {
    "role": str,           # "user" 或 "assistant"
    "content": str,        # 消息内容
    "timestamp": str,      # ISO格式时间戳
    "session_id": str,     # 会话ID
    "message_id": str      # 消息唯一ID (可选)
}

# 用户特有字段
user_fields = {
    "user_id": str,        # 用户ID
    "user_name": str       # 用户名称
}

# 助手特有字段
assistant_fields = {
    "role_id": str,        # 角色ID
    "role_name": str       # 角色名称
}

class MemoryService:
    """记忆服务，负责管理会话历史与构建对话上下文"""
    
    def __init__(
        self, 
        redis_memory: Optional[RedisMemory] = None, 
        mongo_backup: Optional[MongoBackup] = None
    ):
        """初始化记忆服务
        
        Args:
            redis_memory: Redis记忆实现，如不提供则自动创建
            mongo_backup: MongoDB备份服务，如不提供则自动创建
        """
        self.redis_memory = redis_memory or RedisMemory()
        self.mongo_backup = mongo_backup or MongoBackup()
        self.max_context_length = int(os.getenv("MAX_CONTEXT_LENGTH", 40))
        self.message_ttl = int(os.getenv("MESSAGE_TTL", 300))
        logger.info(f"记忆服务初始化完成，最大上下文长度={self.max_context_length}")
    
    async def add_user_message(self, session_id: str, message: str, user_id: Optional[str] = None, user_name: Optional[str] = None) -> None:
        """添加用户消息到记忆"""
        try:
            # 添加到Redis，使用通用接口
            await self.redis_memory.add_message(
                session_id=session_id, 
                role="user", 
                content=message,
                user_id=user_id,
                user_name=user_name
            )
            
            # 异步备份到MongoDB
            backup_task = asyncio.create_task(
                self.mongo_backup.backup_message(
                    session_id=session_id, 
                    role="user", 
                    content=message,
                    user_id=user_id,
                    user_name=user_name
                )
            )
            
            logger.debug(f"用户消息已添加到记忆: {session_id[:10]}..., 用户={user_name or user_id}, 长度={len(message)}")
        except Exception as e:
            logger.error(f"添加用户消息到记忆失败: {e}")
    
    async def add_assistant_message(self, session_id: str, message: str, role_name: str = "assistant", role_id: Optional[str] = None) -> None:
        """添加助手消息到记忆"""
        try:
            # 添加到Redis，使用通用接口与所有参数
            await self.redis_memory.add_message(
                session_id=session_id, 
                role="assistant", 
                content=message,
                role_name=role_name,
                role_id=role_id
            )
            
            # 异步备份到MongoDB，同样传递所有参数
            backup_task = asyncio.create_task(
                self.mongo_backup.backup_message(
                    session_id=session_id, 
                    role="assistant", 
                    content=message,
                    role_name=role_name,
                    role_id=role_id
                )
            )
            
            logger.debug(f"助手消息已添加到记忆: {session_id[:10]}..., 角色={role_name}, 长度={len(message)}")
        except Exception as e:
            logger.error(f"添加助手消息到记忆失败: {e}")
    
    async def build_message_history(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """构建消息历史用于LLM上下文
        
        Args:
            session_id: 会话ID
            limit: 历史消息数量限制，不指定则使用默认值
            
        Returns:
            List[Dict[str, str]]: 格式化后的消息历史
        """
        if not session_id:
            logger.error("无法构建消息历史: session_id不能为空")
            return []
            
        # 使用指定的limit或默认值
        actual_limit = limit or self.max_context_length
        logger.info("构建消息历史", extra={"data": {"limit": actual_limit}})
        
        # 首先从Redis获取最近消息
        messages = await self.redis_memory.get_messages(session_id, actual_limit)
        
        # 检查消息时间顺序
        logger.info(f"消息时间顺序检查: {[msg.get('timestamp', 'no-timestamp') for msg in messages[:5]]}")
        
        # 格式化消息以适应LLM API格式
        formatted_messages = []
        for msg in messages:
            if msg["role"] == "user":
                formatted_messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                formatted_messages.append({"role": "assistant", "content": msg["content"]})
        
        logger.info(f"为AI请求构建上下文: 获取到{len(messages)}条消息")
        # 记录消息摘要
        for i, msg in enumerate(messages[:3]):
            preview = msg["content"][:30] + ("..." if len(msg["content"]) > 30 else "")
            logger.info("消息详情", extra={"data": {"index": i, "role": msg['role'], "preview": preview, "length": len(msg['content'])}})
        
        logger.debug(f"为会话构建了{len(formatted_messages)}条消息历史: session={session_id}")
        logger.info(f"格式化后的消息历史总数: {len(formatted_messages)}")
        
        if formatted_messages:
            logger.info(f"第一条消息: {formatted_messages[0]}")
            logger.info(f"最后一条消息: {formatted_messages[-1]}")
            # 打印完整内容长度统计
            logger.info(f"完整历史长度统计: {[len(msg['content']) for msg in formatted_messages]}")
            logger.info(f"消息历史总字符数: {sum(len(msg['content']) for msg in formatted_messages)}")
            
            # 转换成更易读的日志格式，显示每条消息的概览
            preview_messages = []
            for i, msg in enumerate(formatted_messages):
                preview_messages.append({
                    "index": i,
                    "role": msg["role"],
                    "content_length": len(msg["content"]),
                    "preview": msg["content"][:50] + ("..." if len(msg["content"]) > 50 else "")
                })
            logger.info(f"消息历史预览: {json.dumps(preview_messages, ensure_ascii=False)}")
        
        return formatted_messages
    
    async def get_full_history(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取完整聊天历史（MongoDB存档）
        
        Args:
            session_id: 会话ID
            limit: 返回消息数量限制
            
        Returns:
            List[Dict[str, Any]]: 完整消息历史
        """
        if not session_id:
            logger.error("无法获取完整历史: session_id不能为空")
            return []
            
        return await self.mongo_backup.get_session_history(session_id, limit)
        
    async def clear_session_history(self, session_id: str) -> bool:
        """清除会话的临时历史记录（仅Redis部分）
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 操作是否成功
        """
        if not session_id:
            logger.error("无法清除历史: session_id不能为空")
            return False
            
        result = await self.redis_memory.clear_messages(session_id)
        logger.info(f"已清除会话的Redis历史记录: session={session_id}, 结果={result}")
        return result

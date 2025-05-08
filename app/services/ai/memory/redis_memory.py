"""使用Redis实现的短期记忆存储"""

import os
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, Any, List, Optional

from app.services.storage.redis_service import RedisService
from .base_memory import BaseMemory

logger = logging.getLogger(__name__)

class RedisMemory(BaseMemory):
    """使用Redis实现的短期记忆存储，48小时过期"""
    
    def __init__(self, redis_service: Optional[RedisService] = None):
        """初始化Redis记忆服务
        
        Args:
            redis_service: Redis服务实例，如不提供则自动创建
        """
        self.redis_service = redis_service or RedisService()
        # 设置48小时TTL (秒数)
        self.message_ttl = 60 * 60 * 48  # 48小时
        logger.info(f"初始化Redis记忆服务，TTL={self.message_ttl}秒")

    def _get_session_key(self, session_id: str) -> str:
        """构造会话消息的Redis键"""
        key = f"chat:history:{session_id}"
        logger.debug(f"使用Redis键: {key}")
        return key

    async def add_message(self, session_id: str, role: str, content: str, **kwargs) -> bool:
        """添加消息到Redis列表
        
        Args:
            session_id: 会话ID
            role: 角色 ("user" 或 "assistant")
            content: 消息内容
            **kwargs: 额外字段，如user_id, user_name, role_id, role_name等
            
        Returns:
            bool: 操作是否成功
        """
        try:
            if not session_id:
                logger.error("无法添加消息: session_id不能为空")
                return False
                
            key = self._get_session_key(session_id)
            
            # 创建消息记录
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id
            }
            
            # 添加额外字段
            for k, v in kwargs.items():
                if v is not None:  # 只添加非空值
                    message[k] = v
                
            # 序列化并存储
            serialized = json.dumps(message)
            await self.redis_service.rpush(key, serialized)
            
            # 设置过期时间
            await self.redis_service.expire(key, self.message_ttl)
            logger.debug(f"消息已添加到Redis: {key}, TTL={self.message_ttl}")
            return True
        except Exception as e:
            logger.error(f"添加消息到Redis失败: {str(e)}")
            return False
            
    async def get_messages(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取历史消息，默认最近10条
        
        Args:
            session_id: 会话ID
            limit: 返回消息数量限制
            
        Returns:
            List[Dict[str, Any]]: 消息列表
        """
        try:
            if not session_id:
                logger.error("无法获取消息: session_id不能为空")
                return []
                
            key = self._get_session_key(session_id)
            # 获取列表长度
            length = await self.redis_service.llen(key)
            
            # 确定开始和结束索引
            start = max(0, length - limit)
            end = length - 1
            
            # 获取消息
            raw_messages = await self.redis_service.lrange(key, start, end)
            messages = []
            
            # 反序列化
            for raw in raw_messages:
                try:
                    message = json.loads(raw)
                    messages.append(message)
                except json.JSONDecodeError:
                    logger.warning(f"无法解析Redis消息: {raw}")
            
            logger.debug(f"从Redis获取了{len(messages)}条消息，session={session_id}")
            return messages
        except Exception as e:
            logger.error(f"从Redis获取消息失败: {str(e)}")
            return []
            
    async def clear_messages(self, session_id: str) -> bool:
        """清除历史消息
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 操作是否成功
        """
        try:
            if not session_id:
                logger.error("无法清除消息: session_id不能为空")
                return False
                
            key = self._get_session_key(session_id)
            await self.redis_service.delete(key)
            logger.info(f"已清除会话历史: {session_id}")
            return True
        except Exception as e:
            logger.error(f"清除Redis消息失败: {str(e)}")
            return False

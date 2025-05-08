"""MongoDB消息备份服务"""

import asyncio
from datetime import datetime
import logging
from typing import Dict, Any, List, Optional

from app.services.storage.mongo_service import MongoService

logger = logging.getLogger(__name__)

class MongoBackup:
    """MongoDB消息备份服务 - 长期存储对话历史"""
    
    def __init__(self, mongo_service: Optional[MongoService] = None):
        """初始化MongoDB备份服务
        
        Args:
            mongo_service: MongoDB服务实例，如不提供则自动创建
        """
        self.mongo_service = mongo_service or MongoService()
        self.collection_name = "message_history"
        logger.info(f"初始化MongoDB消息备份服务，集合={self.collection_name}")
        
    async def backup_message(self, session_id: str, role: str, content: str, **kwargs) -> None:
        """异步备份消息到MongoDB
        
        Args:
            session_id: 会话ID
            role: 消息角色 (user/assistant)
            content: 消息内容
            **kwargs: 额外字段
        """
        try:
            # 创建消息文档
            message_doc = {
                "session_id": session_id,
                "role": role,
                "content": content,
                "timestamp": datetime.now()
            }
            
            # 添加额外字段
            for k, v in kwargs.items():
                if v is not None:  # 只添加非空值
                    message_doc[k] = v
            
            # 确保异步插入操作正确执行
            await self.mongo_service.insert_one(self.collection_name, message_doc)
            
            logger.debug(f"消息已备份到MongoDB: {session_id}, {role[:10]}...")
        except Exception as e:
            logger.error(f"备份消息到MongoDB失败: {e}")
    
    async def get_session_history(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取会话的完整历史记录
        
        Args:
            session_id: 会话ID
            limit: 返回消息数量限制
            
        Returns:
            List[Dict[str, Any]]: 消息历史列表
        """
        try:
            if not session_id:
                logger.error("无法获取历史: session_id不能为空")
                return []
                
            query = {"session_id": session_id}
            sort = [("timestamp", 1)]  # 按时间升序
            
            cursor = self.mongo_service.find(
                self.collection_name, 
                query=query, 
                sort=sort,
                limit=limit
            )
            
            if not cursor:
                logger.warning(f"MongoDB查询返回空cursor: session={session_id}")
                return []
                
            messages = await cursor.to_list(length=limit)
            logger.debug(f"从MongoDB获取了{len(messages)}条历史记录，session={session_id}")
            return messages
            
        except Exception as e:
            logger.error(f"从MongoDB获取历史记录失败: {str(e)}")
            return []

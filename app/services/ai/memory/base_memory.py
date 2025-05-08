"""定义记忆存储的基本接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import json

class BaseMemory(ABC):
    """记忆存储抽象基类"""
    
    @abstractmethod
    async def add_message(self, session_id: str, message: Dict[str, Any]) -> bool:
        """添加消息到历史记录
        
        Args:
            session_id: 会话ID
            message: 消息内容字典
            
        Returns:
            bool: 操作是否成功
        """
        pass
    
    @abstractmethod
    async def get_messages(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取历史消息
        
        Args:
            session_id: 会话ID
            limit: 返回消息数量限制
            
        Returns:
            List[Dict[str, Any]]: 消息列表
        """
        pass
    
    @abstractmethod
    async def clear_messages(self, session_id: str) -> bool:
        """清除历史消息
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 操作是否成功
        """
        pass

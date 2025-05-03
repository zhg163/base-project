from typing import Dict, List, Optional, Type, TypeVar, Generic, Any
import json
import uuid
from datetime import datetime

from app.services.storage.redis_service import RedisService
from app.models.entities.base import BaseModel
from app.utils.logging import logger

T = TypeVar('T', bound=BaseModel)

class RedisRepository(Generic[T]):
    """Redis存储库，提供模型的CRUD操作"""
    
    def __init__(self, model_class: Type[T], redis_service: RedisService = None):
        """初始化存储库
        
        Args:
            model_class: 模型类
            redis_service: Redis服务实例，为None时自动创建
        """
        self.model_class = model_class
        self.redis = redis_service or RedisService()
        self.collection_key = model_class.get_collection_key()
    
    def create(self, obj: T) -> T:
        """创建新对象
        
        Args:
            obj: 模型实例
            
        Returns:
            创建后的模型实例（包含ID）
        """
        # 如果没有ID，生成一个
        if not obj.id:
            obj.id = str(uuid.uuid4())
        
        # 设置时间戳
        obj.created_at = datetime.utcnow()
        obj.updated_at = datetime.utcnow()
        
        # 获取对象的Redis键
        key = self.model_class.get_redis_key(obj.id)
        
        # 转换为哈希格式
        hash_data = obj.to_redis_hash()
        
        # 存储对象
        pipe = self.redis.client.pipeline()
        pipe.hmset(key, hash_data)
        
        # 将ID添加到集合中
        pipe.sadd(self.collection_key, obj.id)
        
        # 执行
        pipe.execute()
        logger.debug(f"Created {self.model_class.__name__} with id {obj.id}")
        
        return obj
    
    def get(self, obj_id: str) -> Optional[T]:
        """获取对象
        
        Args:
            obj_id: 对象ID
            
        Returns:
            模型实例，不存在则返回None
        """
        # 获取对象的Redis键
        key = self.model_class.get_redis_key(obj_id)
        
        # 获取哈希数据
        hash_data = self.redis.hgetall(key)
        
        if not hash_data:
            return None
        
        # 转换为模型实例
        try:
            return self.model_class.from_redis_hash(hash_data)
        except Exception as e:
            logger.error(f"Failed to parse {self.model_class.__name__} data: {str(e)}")
            return None
    
    def update(self, obj: T) -> T:
        """更新对象
        
        Args:
            obj: 模型实例
            
        Returns:
            更新后的模型实例
        """
        # 确保对象有ID
        if not obj.id:
            raise ValueError(f"Cannot update {self.model_class.__name__} without ID")
        
        # 检查对象是否存在
        key = self.model_class.get_redis_key(obj.id)
        if not self.redis.exists(key):
            raise ValueError(f"{self.model_class.__name__} with id {obj.id} not found")
        
        # 更新时间戳
        obj.updated_at = datetime.utcnow()
        
        # 转换为哈希格式
        hash_data = obj.to_redis_hash()
        
        # 更新对象
        self.redis.client.hmset(key, hash_data)
        logger.debug(f"Updated {self.model_class.__name__} with id {obj.id}")
        
        return obj
    
    def delete(self, obj_id: str) -> bool:
        """删除对象
        
        Args:
            obj_id: 对象ID
            
        Returns:
            删除成功返回True
        """
        # 获取对象的Redis键
        key = self.model_class.get_redis_key(obj_id)
        
        # 检查对象是否存在
        if not self.redis.exists(key):
            return False
        
        # 删除对象和集合中的ID
        pipe = self.redis.client.pipeline()
        pipe.delete(key)
        pipe.srem(self.collection_key, obj_id)
        pipe.execute()
        
        logger.debug(f"Deleted {self.model_class.__name__} with id {obj_id}")
        return True
    
    def list(self, limit: int = 100, offset: int = 0) -> List[T]:
        """列出对象
        
        Args:
            limit: 返回的最大对象数
            offset: 起始偏移量
            
        Returns:
            对象列表
        """
        # 获取集合中的所有ID
        ids = self.redis.smembers(self.collection_key)
        
        # 应用分页
        paged_ids = list(ids)[offset:offset+limit]
        
        # 批量获取对象
        result = []
        for obj_id in paged_ids:
            obj = self.get(obj_id)
            if obj:
                result.append(obj)
        
        return result
    
    def count(self) -> int:
        """获取对象总数
        
        Returns:
            对象总数
        """
        return len(self.redis.smembers(self.collection_key))
    
    def exists(self, obj_id: str) -> bool:
        """检查对象是否存在
        
        Args:
            obj_id: 对象ID
            
        Returns:
            对象存在返回True
        """
        key = self.model_class.get_redis_key(obj_id)
        return self.redis.exists(key) 
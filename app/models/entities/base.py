from datetime import datetime
from typing import Dict, Any, Optional, Type, TypeVar, ClassVar, Generic
import json
from pydantic import BaseModel as PydanticBaseModel, Field

T = TypeVar('T', bound='BaseModel')

class BaseModel(PydanticBaseModel):
    """基础模型类，提供公共方法"""
    
    id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Redis存储配置
    _redis_key_prefix: ClassVar[str] = "base"  # 在子类中覆盖
    
    @classmethod
    def get_redis_key(cls, obj_id: str) -> str:
        """获取对象在Redis中的键名
        
        Args:
            obj_id: 对象ID
            
        Returns:
            完整的Redis键名
        """
        return f"{cls._redis_key_prefix}:{obj_id}"
    
    @classmethod
    def get_collection_key(cls) -> str:
        """获取集合在Redis中的键名
        
        Returns:
            集合键名
        """
        return f"{cls._redis_key_prefix}:all"
    
    def to_redis_hash(self) -> Dict[str, str]:
        """转换为Redis哈希存储格式
        
        Returns:
            适合Redis哈希存储的键值对
        """
        # 使用模型的dict方法，然后序列化复杂值
        data = self.model_dump()
        result = {}
        
        for key, value in data.items():
            if isinstance(value, (dict, list, tuple, set)):
                result[key] = json.dumps(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            else:
                result[key] = str(value)
        
        return result
    
    @classmethod
    def from_redis_hash(cls: Type[T], data: Dict[str, str]) -> T:
        """从Redis哈希数据创建模型实例
        
        Args:
            data: Redis哈希数据
            
        Returns:
            模型实例
        """
        # 解析复杂类型
        parsed_data = {}
        
        for key, value in data.items():
            # 尝试JSON解析
            try:
                parsed_data[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # 不是JSON，保持原样
                parsed_data[key] = value
        
        # 使用解析后的数据创建模型实例
        return cls(**parsed_data) 
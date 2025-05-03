from datetime import datetime
from typing import Dict, Any, Optional, Type, TypeVar, ClassVar, List
from bson import ObjectId
from pydantic import BaseModel as PydanticBaseModel, Field, field_validator
from pydantic_core import core_schema

T = TypeVar('T', bound='MongoModel')

# 创建自定义的 ObjectId 字段处理
class PyObjectId(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        return core_schema.union_schema([
            core_schema.is_instance_schema(ObjectId),
            core_schema.chain_schema([
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(cls.validate)
            ])
        ])

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        if not isinstance(v, str):
            raise TypeError('ObjectId required')
        try:
            return str(ObjectId(v))
        except ValueError:
            raise ValueError('Invalid ObjectId')

class MongoModel(PydanticBaseModel):
    """MongoDB 基础模型类"""
    
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # MongoDB 存储配置
    _collection_name: ClassVar[str] = "base_collection"  # 在子类中覆盖
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
    
    def model_dump_mongo(self) -> Dict[str, Any]:
        """转换为适合 MongoDB 存储的字典
        
        Returns:
            MongoDB 文档字典
        """
        # 获取模型的字典表示
        data = self.model_dump(by_alias=True)
        
        # 如果没有 ID，则移除它
        if data.get("_id") is None:
            data.pop("_id", None)
        # 如果 ID 是字符串，则转为 ObjectId
        elif isinstance(data["_id"], str):
            data["_id"] = ObjectId(data["_id"])
        
        return data
    
    @classmethod
    def from_mongo(cls: Type[T], data: Dict[str, Any]) -> T:
        """从 MongoDB 文档创建模型实例
        
        Args:
            data: MongoDB 文档
            
        Returns:
            模型实例
        """
        # 深拷贝防止修改原始数据
        import copy
        doc_data = copy.deepcopy(data)
        
        # 处理 _id 字段
        if "_id" in doc_data:
            doc_data["_id"] = str(doc_data["_id"])
        
        # 记录转换前的数据结构（调试用）
        from app.utils.logging import logger
        logger.debug(f"Converting MongoDB doc to {cls.__name__}: {doc_data}")
        
        try:
            # 创建模型实例
            return cls(**doc_data)
        except Exception as e:
            # 转换失败时记录详细信息
            logger.error(f"Failed to convert MongoDB doc to {cls.__name__}: {str(e)}")
            raise 
from typing import Dict, List, Optional, Type, TypeVar, Generic, Any
from datetime import datetime
from bson import ObjectId

from app.services.storage.mongo_service import MongoService
from app.models.entities.mongo_base import MongoModel
from app.utils.logging import logger

T = TypeVar('T', bound=MongoModel)

class MongoRepository(Generic[T]):
    """MongoDB 仓库，提供模型的 CRUD 操作"""
    
    def __init__(self, model_class: Type[T], mongo_service: MongoService = None):
        """初始化仓库
        
        Args:
            model_class: 模型类
            mongo_service: MongoDB 服务实例，为 None 时自动创建
        """
        self.model_class = model_class
        self.mongo = mongo_service or MongoService()
        self.collection_name = model_class._collection_name
    
    async def create(self, obj: T) -> T:
        """异步创建新对象
        
        Args:
            obj: 模型实例
            
        Returns:
            创建后的模型实例（包含 ID）
        """
        # 设置时间戳
        obj.created_at = datetime.utcnow()
        obj.updated_at = datetime.utcnow()
        
        # 转换为 MongoDB 文档格式
        doc = obj.model_dump_mongo()
        
        # 异步插入文档
        import asyncio
        inserted_id = await asyncio.to_thread(self.mongo.insert_one, self.collection_name, doc)
        
        # 更新实例 ID
        if hasattr(obj, "id"):
            obj.id = inserted_id
        
        logger.debug(f"Created {self.model_class.__name__} with id {inserted_id}")
        return obj
    
    async def get(self, obj_id: str) -> Optional[T]:
        """异步获取对象
        
        Args:
            obj_id: 对象 ID
            
        Returns:
            模型实例，不存在则返回 None
        """
        # 使用异步包装同步方法
        import asyncio
        doc = await asyncio.to_thread(self.mongo.find_by_id, self.collection_name, obj_id)
        
        if not doc:
            return None
        
        # 转换为模型实例
        try:
            return self.model_class.from_mongo(doc)
        except Exception as e:
            logger.error(f"Failed to parse {self.model_class.__name__} data: {str(e)}")
            return None
    
    async def find_one(self, filter_dict: Dict[str, Any]) -> Optional[T]:
        """
        异步查询单个文档
        
        Args:
            filter_dict: 查询条件
            
        Returns:
            查询到的文档模型实例，没有找到则返回 None
        """
        try:
            # 将同步调用包装为异步
            result = await self._run_async(
                self.mongo.find_one,
                self.collection_name,
                filter_dict
            )
            
            if not result:
                return None
            
            return self.model_class.from_mongo(result)
        except Exception as e:
            logger.error(f"Error in find_one: {str(e)}")
            return None
    
    async def find_many(self, filter_dict: Dict[str, Any] = None, 
                   sort: List = None, skip: int = 0, 
                   limit: int = 100) -> List[T]:
        """异步查找多个对象"""
        # 异步获取文档
        docs = await self.mongo.find_many(
            self.collection_name, 
            filter_dict=filter_dict,
            sort=sort,
            skip=skip,
            limit=limit
        )
        
        # 转换为模型实例
        result = []
        for doc in docs:
            try:
                result.append(self.model_class.from_mongo(doc))
            except Exception as e:
                logger.error(f"Failed to parse {self.model_class.__name__} data: {str(e)}")
        
        return result
    
    async def update(self, obj: T) -> T:
        """异步更新对象
        
        Args:
            obj: 模型实例
            
        Returns:
            更新后的模型实例
        """
        # 确保对象有 ID
        if not obj.id:
            raise ValueError(f"Cannot update {self.model_class.__name__} without ID")
        
        # 更新时间戳
        obj.updated_at = datetime.utcnow()
        
        # 转换为 MongoDB 文档格式
        doc = obj.model_dump_mongo()
        
        # 移除 _id 字段（不能更新）
        doc_id = doc.pop("_id")
        
        # 异步更新文档
        import asyncio
        success = await asyncio.to_thread(
            self.mongo.update_by_id,
            self.collection_name,
            str(doc_id),
            {"$set": doc}
        )
        
        if not success:
            logger.warning(f"Failed to update {self.model_class.__name__} with id {obj.id}")
        else:
            logger.debug(f"Updated {self.model_class.__name__} with id {obj.id}")
        
        return obj
    
    async def delete(self, obj_id: str) -> bool:
        """异步删除对象
        
        Args:
            obj_id: 对象 ID
            
        Returns:
            删除成功返回 True
        """
        import asyncio
        success = await asyncio.to_thread(self.mongo.delete_by_id, self.collection_name, obj_id)
        
        if success:
            logger.debug(f"Deleted {self.model_class.__name__} with id {obj_id}")
        
        return success
    
    async def count(self, filter_dict: Dict[str, Any] = None) -> int:
        """计算符合条件的对象数量
        
        Args:
            filter_dict: 过滤条件
            
        Returns:
            对象数量
        """
        return self.mongo.count(self.collection_name, filter_dict)
    
    async def _run_async(self, func, *args, **kwargs):
        """将同步函数包装为异步执行"""
        import asyncio
        return await asyncio.to_thread(func, *args, **kwargs)
    
    async def find_by_session_id(self, session_id: str) -> Optional[T]:
        """通过session_id字段查询单个文档
        
        Args:
            session_id: 会话ID
            
        Returns:
            实体对象，如果不存在则返回None
        """
        return await self.find_one({"session_id": session_id}) 
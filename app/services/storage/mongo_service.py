from typing import Dict, List, Any, Optional, Type, TypeVar, Generic
import pymongo
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from bson import ObjectId
from contextlib import contextmanager

from app.core.config import settings
from app.utils.logging import logger

T = TypeVar('T')

class MongoService:
    """MongoDB 基础服务，提供与 MongoDB 交互的基本能力"""
    
    def __init__(self, uri: str = None, db_name: str = None):
        """初始化 MongoDB 服务
        
        Args:
            uri: MongoDB 连接字符串，为 None 时使用配置
            db_name: 数据库名称，为 None 时使用配置
        """
        self.uri = uri or settings.MONGODB_URL
        self.db_name = db_name or settings.MONGODB_DB_NAME
        
        # 创建安全的日志版本（隐藏密码）
        safe_uri = self._get_safe_connection_string(self.uri)
        
        # 延迟初始化客户端
        self._client = None
        self._db = None
        logger.info(f"MongoDB service initialized with URI: {safe_uri}, DB: {self.db_name}")
    
    @property
    def client(self) -> MongoClient:
        """获取 MongoDB 客户端实例"""
        if self._client is None:
            safe_uri = self._get_safe_connection_string(self.uri)
            logger.info(f"Creating new MongoDB connection to {safe_uri}")
            try:
                self._client = MongoClient(self.uri)
                # 验证连接是否成功
                self._client.admin.command('ping')
                logger.info(f"MongoDB connection established successfully")
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {str(e)}")
                raise
        return self._client
    
    @property
    def db(self) -> Database:
        """获取数据库实例"""
        if self._db is None:
            self._db = self.client[self.db_name]
        return self._db
    
    def get_collection(self, name: str) -> Collection:
        """获取集合
        
        Args:
            name: 集合名称
            
        Returns:
            MongoDB 集合对象
        """
        return self.db[name]
    
    @contextmanager
    def transaction(self):
        """事务上下文管理器
        
        使用示例:
        with mongo_service.transaction() as session:
            # 在事务中执行操作
            collection.insert_one({"key": "value"}, session=session)
        """
        with self.client.start_session() as session:
            with session.start_transaction():
                try:
                    yield session
                    logger.debug("MongoDB transaction committed")
                except Exception as e:
                    logger.error(f"MongoDB transaction aborted: {str(e)}")
                    raise
    
    # 基本文档操作
    def insert_one(self, collection_name: str, document: Dict) -> str:
        """插入单个文档
        
        Args:
            collection_name: 集合名称
            document: 要插入的文档
            
        Returns:
            插入文档的ID
        """
        try:
            collection = self.get_collection(collection_name)
            result = collection.insert_one(document)
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Failed to insert document into {collection_name}: {str(e)}")
            raise
    
    def find_one(self, collection_name: str, filter_dict: Dict = None, 
                projection: Dict = None) -> Optional[Dict]:
        """查找单个文档
        
        Args:
            collection_name: 集合名称
            filter_dict: 过滤条件
            projection: 投影（指定返回的字段）
            
        Returns:
            匹配的文档，未找到则返回 None
        """
        try:
            collection = self.get_collection(collection_name)
            return collection.find_one(filter_dict or {}, projection)
        except PyMongoError as e:
            logger.error(f"Failed to find document in {collection_name}: {str(e)}")
            return None
    
    def find_by_id(self, collection_name: str, doc_id: str, 
                  projection: Dict = None) -> Optional[Dict]:
        """根据 ID 查找文档
        
        Args:
            collection_name: 集合名称
            doc_id: 文档 ID
            projection: 投影（指定返回的字段）
            
        Returns:
            匹配的文档，未找到则返回 None
        """
        try:
            # 转换字符串 ID 为 ObjectId
            object_id = ObjectId(doc_id)
            return self.find_one(collection_name, {"_id": object_id}, projection)
        except (PyMongoError, ValueError) as e:
            logger.error(f"Failed to find document by ID in {collection_name}: {str(e)}")
            return None
    
    async def find_many(self, collection_name: str, filter_dict: Dict = None, 
                projection: Dict = None, sort: List = None, 
                skip: int = 0, limit: int = 0) -> List[Dict]:
        """查找多个文档
        
        Args:
            collection_name: 集合名称
            filter_dict: 过滤条件
            projection: 投影（指定返回的字段）
            sort: 排序条件，如 [("field", 1)]
            skip: 跳过的文档数
            limit: 返回的最大文档数，0 表示不限制
            
        Returns:
            匹配文档的列表
        """
        try:
            collection = self.get_collection(collection_name)
            cursor = collection.find(filter_dict or {}, projection)
            
            if sort:
                cursor = cursor.sort(sort)
            
            if skip:
                cursor = cursor.skip(skip)
                
            if limit:
                cursor = cursor.limit(limit)
                
            return list(cursor)
        except PyMongoError as e:
            logger.error(f"Failed to find documents in {collection_name}: {str(e)}")
            return []
    
    def update_one(self, collection_name: str, filter_dict: Dict, 
                  update_dict: Dict, upsert: bool = False) -> bool:
        """更新单个文档
        
        Args:
            collection_name: 集合名称
            filter_dict: 过滤条件
            update_dict: 更新操作，如 {"$set": {"field": "value"}}
            upsert: 如果文档不存在是否插入
            
        Returns:
            更新成功返回 True
        """
        try:
            collection = self.get_collection(collection_name)
            result = collection.update_one(filter_dict, update_dict, upsert=upsert)
            return result.modified_count > 0 or (upsert and result.upserted_id is not None)
        except PyMongoError as e:
            logger.error(f"Failed to update document in {collection_name}: {str(e)}")
            return False
    
    def update_by_id(self, collection_name: str, doc_id: str, 
                    update_dict: Dict) -> bool:
        """根据 ID 更新文档
        
        Args:
            collection_name: 集合名称
            doc_id: 文档 ID
            update_dict: 更新操作，如 {"$set": {"field": "value"}}
            
        Returns:
            更新成功返回 True
        """
        try:
            # 转换字符串 ID 为 ObjectId
            object_id = ObjectId(doc_id)
            return self.update_one(collection_name, {"_id": object_id}, update_dict)
        except (PyMongoError, ValueError) as e:
            logger.error(f"Failed to update document by ID in {collection_name}: {str(e)}")
            return False
    
    def delete_one(self, collection_name: str, filter_dict: Dict) -> bool:
        """删除单个文档
        
        Args:
            collection_name: 集合名称
            filter_dict: 过滤条件
            
        Returns:
            删除成功返回 True
        """
        try:
            collection = self.get_collection(collection_name)
            result = collection.delete_one(filter_dict)
            return result.deleted_count > 0
        except PyMongoError as e:
            logger.error(f"Failed to delete document in {collection_name}: {str(e)}")
            return False
    
    def delete_by_id(self, collection_name: str, doc_id: str) -> bool:
        """根据 ID 删除文档
        
        Args:
            collection_name: 集合名称
            doc_id: 文档 ID
            
        Returns:
            删除成功返回 True
        """
        try:
            # 转换字符串 ID 为 ObjectId
            object_id = ObjectId(doc_id)
            return self.delete_one(collection_name, {"_id": object_id})
        except (PyMongoError, ValueError) as e:
            logger.error(f"Failed to delete document by ID in {collection_name}: {str(e)}")
            return False
    
    async def count(self, collection_name: str, filter_dict: Dict = None) -> int:
        """计算符合条件的文档数量
        
        Args:
            collection_name: 集合名称
            filter_dict: 过滤条件
            
        Returns:
            文档数量
        """
        try:
            collection = self.get_collection(collection_name)
            return collection.count_documents(filter_dict or {})
        except PyMongoError as e:
            logger.error(f"Failed to count documents in {collection_name}: {str(e)}")
            return 0

    def _get_safe_connection_string(self, uri: str) -> str:
        """创建用于日志的安全连接字符串（隐藏密码）"""
        if not uri or "://" not in uri:
            return uri
        
        try:
            # 例如将 mongodb://user:password@host/ 转换为 mongodb://user:***@host/
            parts = uri.split("://", 1)
            protocol = parts[0]
            rest = parts[1]
            
            if "@" in rest:
                auth_host = rest.split("@", 1)
                auth = auth_host[0]
                host = auth_host[1]
                
                if ":" in auth:
                    user_pass = auth.split(":", 1)
                    user = user_pass[0]
                    return f"{protocol}://{user}:***@{host}"
            
            return uri
        except:
            # 如果解析失败，返回无法解析的提示
            return "[uri-with-credentials]"

def get_mongo_service():
    """
    获取MongoDB服务实例
    
    Returns:
        MongoService: MongoDB服务实例
    """
    # 单例模式，确保只创建一个MongoDB连接
    if not hasattr(get_mongo_service, "_instance"):
        mongo_service = MongoService(
            uri=settings.MONGODB_URL,
            db_name=settings.MONGODB_DB_NAME
        )
        get_mongo_service._instance = mongo_service
    
    return get_mongo_service._instance

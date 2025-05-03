import json
from typing import Any, Dict, List, Optional, TypeVar, Generic, Type, Union, Set
import redis
from redis.connection import ConnectionPool
from redis.exceptions import RedisError
from contextlib import contextmanager

from app.core.config import settings
from app.utils.logging import logger

T = TypeVar('T')

class RedisService:
    """Redis基础服务，提供与Redis交互的基本能力"""
    
    def __init__(self, host: str = None, port: int = None, 
                db: int = None, password: str = None, 
                decode_responses: bool = True, pool_size: int = 10):
        """初始化Redis服务
        
        Args:
            host: Redis主机地址，为None时使用配置
            port: Redis端口，为None时使用配置
            db: Redis数据库编号，为None时使用配置
            password: Redis密码，为None时使用配置
            decode_responses: 是否自动解码为字符串
            pool_size: 连接池大小
        """
        self.host = host or settings.REDIS_HOST
        self.port = port or settings.REDIS_PORT
        self.db = db if db is not None else settings.REDIS_DB
        self.password = password or settings.REDIS_PASSWORD
        self.decode_responses = decode_responses
        
        # 创建连接池
        self.pool = ConnectionPool(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            decode_responses=self.decode_responses,
            max_connections=pool_size
        )
        
        # 延迟创建Redis客户端
        self._client = None
        logger.info(f"Redis service initialized for {self.host}:{self.port} db:{self.db}")
    
    @property
    def client(self) -> redis.Redis:
        """获取Redis客户端实例"""
        if self._client is None:
            self._client = redis.Redis(connection_pool=self.pool)
        return self._client
    
    @contextmanager
    def get_connection(self):
        """获取Redis连接上下文管理器"""
        try:
            yield self.client
            logger.debug("Redis connection used and returned to pool")
        except RedisError as e:
            logger.error(f"Redis operation failed: {str(e)}", exc_info=e)
            raise
    
    # 基本操作 - 字符串
    def set(self, key: str, value: Any, ex: int = None, 
            nx: bool = False, xx: bool = False) -> bool:
        """设置字符串值
        
        Args:
            key: 键名
            value: 需要存储的值
            ex: 过期时间(秒)
            nx: 仅在键不存在时设置
            xx: 仅在键已存在时设置
            
        Returns:
            设置成功返回True
        """
        try:
            with self.get_connection() as conn:
                # 如果值不是字符串，尝试JSON序列化
                if not isinstance(value, (str, bytes, int, float)):
                    value = json.dumps(value)
                    
                return conn.set(key, value, ex=ex, nx=nx, xx=xx)
        except Exception as e:
            logger.error(f"Failed to set key {key}: {str(e)}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取字符串值
        
        Args:
            key: 键名
            default: 默认值，若键不存在则返回
            
        Returns:
            存储的值，若不存在则返回default
        """
        try:
            with self.get_connection() as conn:
                value = conn.get(key)
                if value is None:
                    return default
                    
                # 尝试作为JSON解析
                try:
                    return json.loads(value)
                except (TypeError, json.JSONDecodeError):
                    return value
        except Exception as e:
            logger.error(f"Failed to get key {key}: {str(e)}")
            return default
    
    def delete(self, *keys) -> int:
        """删除一个或多个键
        
        Args:
            keys: 要删除的键名
            
        Returns:
            删除的键数量
        """
        try:
            with self.get_connection() as conn:
                return conn.delete(*keys)
        except Exception as e:
            logger.error(f"Failed to delete keys {keys}: {str(e)}")
            return 0
    
    def exists(self, key: str) -> bool:
        """检查键是否存在
        
        Args:
            key: 键名
            
        Returns:
            键存在返回True，否则返回False
        """
        try:
            with self.get_connection() as conn:
                return bool(conn.exists(key))
        except Exception as e:
            logger.error(f"Failed to check existence of key {key}: {str(e)}")
            return False
    
    def expire(self, key: str, seconds: int) -> bool:
        """设置键的过期时间
        
        Args:
            key: 键名
            seconds: 过期秒数
            
        Returns:
            设置成功返回True
        """
        try:
            with self.get_connection() as conn:
                return bool(conn.expire(key, seconds))
        except Exception as e:
            logger.error(f"Failed to set expiry for key {key}: {str(e)}")
            return False
    
    # 哈希操作
    def hset(self, name: str, key: str, value: Any) -> int:
        """设置哈希表中的字段值
        
        Args:
            name: 哈希表名
            key: 字段名
            value: 字段值
            
        Returns:
            新字段返回1，更新字段返回0
        """
        try:
            with self.get_connection() as conn:
                # 如果值不是字符串，尝试JSON序列化
                if not isinstance(value, (str, bytes, int, float)):
                    value = json.dumps(value)
                return conn.hset(name, key, value)
        except Exception as e:
            logger.error(f"Failed to set hash field {name}:{key}: {str(e)}")
            return 0
    
    def hget(self, name: str, key: str, default: Any = None) -> Any:
        """获取哈希表中字段的值
        
        Args:
            name: 哈希表名
            key: 字段名
            default: 默认值，字段不存在时返回
            
        Returns:
            字段值，不存在则返回default
        """
        try:
            with self.get_connection() as conn:
                value = conn.hget(name, key)
                if value is None:
                    return default
                
                # 尝试作为JSON解析
                try:
                    return json.loads(value)
                except (TypeError, json.JSONDecodeError):
                    return value
        except Exception as e:
            logger.error(f"Failed to get hash field {name}:{key}: {str(e)}")
            return default
    
    def hdel(self, name: str, *keys) -> int:
        """删除哈希表中的一个或多个字段
        
        Args:
            name: 哈希表名
            keys: 字段名列表
            
        Returns:
            删除的字段数量
        """
        try:
            with self.get_connection() as conn:
                return conn.hdel(name, *keys)
        except Exception as e:
            logger.error(f"Failed to delete hash fields {name}:{keys}: {str(e)}")
            return 0
    
    def hgetall(self, name: str) -> Dict:
        """获取哈希表中所有字段和值
        
        Args:
            name: 哈希表名
            
        Returns:
            包含所有字段和值的字典
        """
        try:
            with self.get_connection() as conn:
                result = conn.hgetall(name)
                
                # 尝试解析所有值为JSON
                parsed = {}
                for key, value in result.items():
                    try:
                        parsed[key] = json.loads(value)
                    except (TypeError, json.JSONDecodeError):
                        parsed[key] = value
                return parsed
        except Exception as e:
            logger.error(f"Failed to get all hash fields for {name}: {str(e)}")
            return {}
    
    # 列表操作
    def lpush(self, name: str, *values) -> int:
        """将一个或多个值推入列表左端
        
        Args:
            name: 列表名
            values: 值列表
            
        Returns:
            操作后列表长度
        """
        try:
            with self.get_connection() as conn:
                # 序列化非基本类型值
                serialized = []
                for value in values:
                    if not isinstance(value, (str, bytes, int, float)):
                        serialized.append(json.dumps(value))
                    else:
                        serialized.append(value)
                return conn.lpush(name, *serialized)
        except Exception as e:
            logger.error(f"Failed to push to list {name}: {str(e)}")
            return 0
    
    def rpush(self, name: str, *values) -> int:
        """将一个或多个值推入列表右端
        
        Args:
            name: 列表名
            values: 值列表
            
        Returns:
            操作后列表长度
        """
        try:
            with self.get_connection() as conn:
                # 序列化非基本类型值
                serialized = []
                for value in values:
                    if not isinstance(value, (str, bytes, int, float)):
                        serialized.append(json.dumps(value))
                    else:
                        serialized.append(value)
                return conn.rpush(name, *serialized)
        except Exception as e:
            logger.error(f"Failed to push to list {name}: {str(e)}")
            return 0
    
    def lrange(self, name: str, start: int, end: int) -> List:
        """获取列表指定范围内的元素
        
        Args:
            name: 列表名
            start: 起始索引
            end: 结束索引
            
        Returns:
            指定范围内的元素列表
        """
        try:
            with self.get_connection() as conn:
                result = conn.lrange(name, start, end)
                
                # 尝试解析所有值为JSON
                parsed = []
                for value in result:
                    try:
                        parsed.append(json.loads(value))
                    except (TypeError, json.JSONDecodeError):
                        parsed.append(value)
                return parsed
        except Exception as e:
            logger.error(f"Failed to get range from list {name}: {str(e)}")
            return []
    
    # 集合操作
    def sadd(self, name: str, *values) -> int:
        """向集合添加一个或多个成员
        
        Args:
            name: 集合名
            values: 值列表
            
        Returns:
            添加的成员数量
        """
        try:
            with self.get_connection() as conn:
                # 序列化非基本类型值
                serialized = []
                for value in values:
                    if not isinstance(value, (str, bytes, int, float)):
                        serialized.append(json.dumps(value))
                    else:
                        serialized.append(value)
                return conn.sadd(name, *serialized)
        except Exception as e:
            logger.error(f"Failed to add to set {name}: {str(e)}")
            return 0
    
    def smembers(self, name: str) -> Set:
        """获取集合中的所有成员
        
        Args:
            name: 集合名
            
        Returns:
            包含所有成员的集合
        """
        try:
            with self.get_connection() as conn:
                result = conn.smembers(name)
                
                # 尝试解析所有值为JSON
                parsed = set()
                for value in result:
                    try:
                        # JSON解析后可能不是可哈希类型，转为字符串
                        parsed_value = json.loads(value)
                        if isinstance(parsed_value, (dict, list)):
                            parsed.add(value)  # 保留原始字符串
                        else:
                            parsed.add(parsed_value)
                    except (TypeError, json.JSONDecodeError):
                        parsed.add(value)
                return parsed
        except Exception as e:
            logger.error(f"Failed to get members from set {name}: {str(e)}")
            return set()
    
    def srem(self, name: str, *values) -> int:
        """从集合中移除一个或多个成员
        
        Args:
            name: 集合名
            values: 要移除的成员列表
            
        Returns:
            移除的成员数量
        """
        try:
            with self.get_connection() as conn:
                # 序列化非基本类型值
                serialized = []
                for value in values:
                    if not isinstance(value, (str, bytes, int, float)):
                        serialized.append(json.dumps(value))
                    else:
                        serialized.append(value)
                return conn.srem(name, *serialized)
        except Exception as e:
            logger.error(f"Failed to remove from set {name}: {str(e)}")
            return 0

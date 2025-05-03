from typing import Any, Optional, Callable, Type, TypeVar, Generic
import time
import hashlib
import inspect
import pickle
from functools import wraps

from app.services.storage.redis_service import RedisService
from app.utils.logging import logger

T = TypeVar('T')

class CacheService:
    """基于Redis的缓存服务"""
    
    def __init__(self, redis_service: RedisService = None, prefix: str = "cache"):
        """初始化缓存服务
        
        Args:
            redis_service: Redis服务实例，为None时自动创建
            prefix: 缓存键前缀
        """
        self.redis = redis_service or RedisService()
        self.prefix = prefix
    
    def _make_key(self, key: str) -> str:
        """生成带前缀的键名
        
        Args:
            key: 原始键名
            
        Returns:
            带前缀的键名
        """
        return f"{self.prefix}:{key}"
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值
        
        Args:
            key: 缓存键名
            default: 默认值
            
        Returns:
            缓存的值，不存在则返回default
        """
        return self.redis.get(self._make_key(key), default)
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """设置缓存值
        
        Args:
            key: 缓存键名
            value: 要缓存的值
            ttl: 过期时间(秒)
            
        Returns:
            设置成功返回True
        """
        return self.redis.set(self._make_key(key), value, ex=ttl)
    
    def delete(self, key: str) -> bool:
        """删除缓存值
        
        Args:
            key: 缓存键名
            
        Returns:
            删除成功返回True
        """
        return bool(self.redis.delete(self._make_key(key)))
    
    def exists(self, key: str) -> bool:
        """检查缓存键是否存在
        
        Args:
            key: 缓存键名
            
        Returns:
            键存在返回True
        """
        return self.redis.exists(self._make_key(key))
    
    def cached(self, ttl: int = 3600, key_prefix: str = None):
        """函数结果缓存装饰器
        
        Args:
            ttl: 缓存过期时间(秒)
            key_prefix: 缓存键前缀，默认为函数名
            
        Returns:
            装饰器函数
        """
        def decorator(func):
            # 获取函数签名
            sig = inspect.signature(func)
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 生成基于参数的缓存键
                prefix = key_prefix or func.__name__
                # 使用有序绑定参数来生成键
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                
                # 排除self或cls参数(如果存在)
                cache_args = dict(bound_args.arguments)
                if 'self' in cache_args:
                    del cache_args['self']
                if 'cls' in cache_args:
                    del cache_args['cls']
                
                # 生成键
                key_parts = [prefix]
                
                # 添加位置参数
                for arg in args:
                    if not isinstance(arg, (str, int, float, bool, type(None))):
                        # 复杂类型使用内存地址，无法缓存
                        continue
                    key_parts.append(str(arg))
                
                # 添加关键字参数
                for k, v in sorted(cache_args.items()):
                    if not isinstance(v, (str, int, float, bool, type(None))):
                        # 复杂类型使用内存地址，无法缓存
                        continue
                    key_parts.append(f"{k}={v}")
                
                # 生成最终键名
                key_str = ":".join(key_parts)
                cache_key = hashlib.md5(key_str.encode()).hexdigest()
                
                # 检查缓存
                cached_result = self.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Cache hit for {func.__name__} with key {cache_key}")
                    return cached_result
                
                # 缓存未命中，执行函数
                logger.debug(f"Cache miss for {func.__name__} with key {cache_key}")
                result = func(*args, **kwargs)
                
                # 缓存结果
                self.set(cache_key, result, ttl=ttl)
                return result
            
            return wrapper
        
        return decorator 
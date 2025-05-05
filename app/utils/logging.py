import json
import logging
import sys
import time
import uuid
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union

from fastapi import Request
from pydantic import BaseModel

from app.core.config import settings


class LogConfig(BaseModel):
    """日志配置模型"""
    
    LOGGER_NAME: str = "ai_project"
    LOG_FORMAT: str = "%(levelprefix)s | %(asctime)s | %(message)s"
    LOG_LEVEL: str = "INFO"
    
    # 文件日志配置
    LOG_FILE: Optional[str] = None
    LOG_FILE_ROTATION: str = "20 MB"
    LOG_FILE_RETENTION: str = "1 month"
    
    # JSON格式化配置
    JSON_LOGS: bool = True
    
    # 输出目标
    CONSOLE_LOG: bool = True


class JsonFormatter(logging.Formatter):
    """JSON格式化器"""
    
    def __init__(self, **kwargs):
        super().__init__()
        self.extras = kwargs
    
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加请求ID（如果存在）
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id
            
        # 添加额外字段
        for key, value in self.extras.items():
            log_record[key] = value
            
        # 添加异常信息（如果存在）
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        # 添加额外的自定义字段
        if hasattr(record, "data") and record.data:
            log_record.update(record.data)
        
        return json.dumps(log_record, ensure_ascii=False)


class RequestIdFilter(logging.Filter):
    """请求ID过滤器，用于在日志记录中添加请求ID"""
    
    def __init__(self, request_id=None):
        super().__init__()
        self.request_id = request_id or str(uuid.uuid4())
    
    def filter(self, record):
        record.request_id = self.request_id
        return True


def get_logger(name: str = None, request_id: str = None) -> logging.Logger:
    """获取配置好的日志记录器
    
    Args:
        name: 日志记录器名称
        request_id: 请求ID，用于跟踪请求
        
    Returns:
        配置好的日志记录器
    """
    config = LogConfig()
    name = name or config.LOGGER_NAME
    logger = logging.getLogger(name)
    
    # 避免重复配置
    if logger.handlers:
        return logger
    
    # 设置日志级别
    level = getattr(logging, config.LOG_LEVEL)
    logger.setLevel(level)
    
    # 添加请求ID过滤器
    if request_id:
        logger.addFilter(RequestIdFilter(request_id))
    
    # 控制台处理器
    if config.CONSOLE_LOG:
        console_handler = logging.StreamHandler(sys.stdout)
        if config.JSON_LOGS:
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(config.LOG_FORMAT)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 文件处理器
    if config.LOG_FILE:
        try:
            from logging.handlers import RotatingFileHandler
            
            file_handler = RotatingFileHandler(
                filename=config.LOG_FILE,
                maxBytes=int(config.LOG_FILE_ROTATION.split()[0]) * 1024 * 1024,
                backupCount=5,
            )
            
            if config.JSON_LOGS:
                formatter = JsonFormatter()
            else:
                formatter = logging.Formatter(config.LOG_FORMAT)
                
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.error(f"Failed to set up file logging: {e}")
    
    return logger


# 性能日志装饰器
def log_performance(logger=None):
    """记录函数执行性能的装饰器
    
    Args:
        logger: 日志记录器，如果未提供则创建一个新的
        
    Returns:
        装饰过的函数
    """
    def decorator(func):
        _logger = logger or get_logger(func.__module__)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            _logger.info(
                f"Performance: {func.__name__}",
                extra={
                    "data": {
                        "function": func.__name__,
                        "execution_time_ms": round(execution_time * 1000, 2),
                    }
                }
            )
            return result
            
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            _logger.info(
                f"Performance: {func.__name__}",
                extra={
                    "data": {
                        "function": func.__name__,
                        "execution_time_ms": round(execution_time * 1000, 2),
                    }
                }
            )
            return result
            
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# AI操作日志中间件
class AIOperationLogMiddleware:
    """记录AI操作的中间件"""
    
    def __init__(self, app):
        self.app = app
        self.logger = get_logger("ai_operations")
    
    async def __call__(self, request: Request, call_next):
        # 生成请求ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # 获取带请求ID的日志记录器
        logger = get_logger("ai_operations", request_id)
        
        # 记录请求开始
        path = request.url.path
        method = request.method
        
        logger.info(
            f"Request started: {method} {path}",
            extra={
                "data": {
                    "method": method,
                    "path": path,
                    "client_ip": request.client.host,
                }
            }
        )
        
        # 处理请求
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # 记录请求完成
        status_code = response.status_code
        
        logger.info(
            f"Request completed: {method} {path} {status_code}",
            extra={
                "data": {
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "process_time_ms": round(process_time * 1000, 2),
                }
            }
        )
        
        return response


# 日志上下文管理器
class LogContext:
    """日志上下文管理器，用于在代码块中添加额外的日志上下文"""
    
    def __init__(self, **kwargs):
        self.extra = kwargs
        self.logger = get_logger()
        self.old_factory = logging.getLogRecordFactory()
    
    def __enter__(self):
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            record.data = getattr(record, "data", {})
            record.data.update(self.extra)
            return record
            
        logging.setLogRecordFactory(record_factory)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)


# AI模型日志记录器
class AILogger:
    """专门用于记录AI模型操作的日志记录器"""
    
    def __init__(self, model_id: str = None, request_id: str = None):
        self.model_id = model_id
        self.logger = get_logger("ai_model", request_id)
    
    def log_prompt(self, prompt: str, role_id: str = None, tokens: int = None):
        """记录发送到模型的提示词
        
        Args:
            prompt: 提示词内容
            role_id: 角色ID
            tokens: 提示词的token数量
        """
        self.logger.info(
            f"Prompt sent to {self.model_id or 'model'}",
            extra={
                "data": {
                    "model_id": self.model_id,
                    "role_id": role_id,
                    "tokens": tokens,
                    "prompt_preview": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                }
            }
        )
    
    def log_completion(self, completion: str, tokens: int = None, latency: float = None):
        """记录模型的回复
        
        Args:
            completion: 模型回复内容
            tokens: 回复的token数量
            latency: 生成回复的延迟时间(ms)
        """
        self.logger.info(
            f"Completion received from {self.model_id or 'model'}",
            extra={
                "data": {
                    "model_id": self.model_id,
                    "tokens": tokens,
                    "latency_ms": latency,
                    "completion_preview": completion[:100] + "..." if len(completion) > 100 else completion,
                }
            }
        )
    
    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """记录模型调用错误
        
        Args:
            error: 异常对象
            context: 额外的上下文信息
        """
        self.logger.error(
            f"Error in {self.model_id or 'model'}: {str(error)}",
            exc_info=error,
            extra={"data": {"model_id": self.model_id, "context": context or {}}}
        )
    
    def log_rag_retrieval(self, query: str, doc_count: int, latency: float = None):
        """记录RAG检索操作
        
        Args:
            query: 检索查询
            doc_count: 检索到的文档数量
            latency: 检索操作的延迟时间(ms)
        """
        self.logger.info(
            "RAG document retrieval",
            extra={
                "data": {
                    "query_preview": query[:100] + "..." if len(query) > 100 else query,
                    "doc_count": doc_count,
                    "latency_ms": latency,
                }
            }
        )


# 导入标准库
import asyncio

# 初始化默认日志记录器
logger = get_logger("ai_project")

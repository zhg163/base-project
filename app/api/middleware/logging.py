from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
import uuid
import json
from typing import Callable

from app.utils.logging import get_logger
from app.core.config import settings


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件，记录每个HTTP请求的信息"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成请求ID并存储在请求状态中
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # 获取带请求ID的日志记录器
        logger = get_logger("api", request_id)
        
        # 记录请求信息
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else None
        
        logger.info(
            f"Request started: {method} {path}",
            extra={
                "data": {
                    "method": method,
                    "path": path,
                    "query_params": str(request.query_params),
                    "client_ip": client_ip,
                }
            }
        )
        
        # 可选择记录请求体（注意可能包含敏感信息）
        if settings.LOG_REQUEST_BODY:
            try:
                body = await request.body()
                if body:
                    body_str = body.decode("utf-8")
                    if len(body_str) > 1000:
                        body_str = body_str[:1000] + "..."
                    logger.debug("Request body", extra={"data": {"body": body_str}})
                # 重置请求体以便后续处理
                await request.body()
            except Exception as e:
                logger.warning(f"Failed to log request body: {str(e)}")
        
        # 处理请求并计时
        start_time = time.time()
        
        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000
            
            # 记录响应信息
            status_code = response.status_code
            
            log_level = "info"
            if status_code >= 500:
                log_level = "error"
            elif status_code >= 400:
                log_level = "warning"
                
            getattr(logger, log_level)(
                f"Request completed: {request.method} {request.url.path} {status_code}",
                extra={"request_info": {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "process_time_ms": process_time
                }}
            )
            
            return response
        except Exception as exc:
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                exc_info=exc,
                extra={
                    "data": {
                        "method": request.method,
                        "path": request.url.path,
                        "process_time_ms": round(process_time, 2),
                        "error": str(exc),
                    }
                }
            )
            raise 
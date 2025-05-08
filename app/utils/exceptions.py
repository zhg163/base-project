import functools
import traceback
from app.utils.logging import logger, merge_extra_data

def handle_exceptions(logger):
    """API路由异常处理装饰器"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # 使用安全的合并函数和不同的字段名避免冲突
                extra = merge_extra_data({
                    'data': {
                        'error_message': str(e),
                        'error_type': type(e).__name__
                    }
                })
                logger.error(f"路由处理异常: {str(e)}", 
                             exc_info=True, 
                             extra=extra)
                raise
        return wrapper
    return decorator 
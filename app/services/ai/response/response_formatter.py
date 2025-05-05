from typing import Dict, Any, Optional, AsyncGenerator
import json

class ResponseFormatter:
    """响应格式化器，处理模型输出的格式化"""
    
    @staticmethod
    def format_response(response: Dict[str, Any], 
                        session_id: Optional[str] = None,
                        request_id: Optional[str] = None) -> Dict[str, Any]:
        """格式化基础响应
        
        Args:
            response: 模型原始响应
            session_id: 会话ID
            request_id: 请求ID
            
        Returns:
            Dict[str, Any]: 格式化后的响应
        """
        formatted = {
            "content": response.get("content", ""),
            "model": response.get("model", "unknown"),
            "finish_reason": response.get("finish_reason", "stop"),
        }
        
        if session_id:
            formatted["session_id"] = session_id
            
        if request_id:
            formatted["request_id"] = request_id
            
        return formatted
    
    @staticmethod
    def format_error(error_message: str, 
                    code: int = 500,
                    request_id: Optional[str] = None) -> Dict[str, Any]:
        """格式化错误响应
        
        Args:
            error_message: 错误信息
            code: 错误代码
            request_id: 请求ID
            
        Returns:
            Dict[str, Any]: 格式化后的错误响应
        """
        error_response = {
            "error": {
                "message": error_message,
                "code": code
            }
        }
        
        if request_id:
            error_response["request_id"] = request_id
            
        return error_response

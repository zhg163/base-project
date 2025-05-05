import uuid
import os
from typing import Dict, Any, Optional, List, AsyncGenerator
from datetime import datetime
from langchain_core.exceptions import OutputParserException
import json

from .ai.llm.llm_factory import LLMFactory
from .ai.prompt.prompt_service import PromptService
from .ai.response.response_formatter import ResponseFormatter

class ChatService:
    """聊天服务，整合各个AI组件提供聊天功能"""
    
    def __init__(self):
        self.llm_factory = LLMFactory()
        self.prompt_service = PromptService()
        self.response_formatter = ResponseFormatter()
    
    async def process_message(self, 
                             message: str, 
                             session_id: Optional[str] = None,
                             model_type: Optional[str] = None,
                             role_name: str = "assistant",
                             system_prompt: Optional[str] = None,
                             temperature: float = 0.7) -> Dict[str, Any]:
        """处理用户消息并返回AI回复"""

        print(f"处理用户消息-1-model_type: {model_type}")
        # 在方法内部处理默认值
        #if model_type is None:
        model_type = os.getenv("DEFAULT_MODEL_TYPE", "deepseek")
        
        print(f"处理用户消息-2-model_type: {model_type}")
        # 生成会话ID和请求ID
        if not session_id:
            session_id = str(uuid.uuid4())
        
        request_id = str(uuid.uuid4())
        
        try:
            # 获取LLM服务
            llm_service = self.llm_factory.get_llm_service(model_type)
            
            # 获取提示词
            if not system_prompt:
                system_prompt = self.prompt_service.get_system_prompt(role_name)
            
            # 生成回复 (不使用历史记录)
            response = await llm_service.generate(
                message=message,
                system_prompt=system_prompt,
                temperature=temperature,
                history=None  # 步骤1不包含历史记录功能
            )
            
            # 检查是否有错误
            if "error" in response:
                return self.response_formatter.format_error(
                    error_message=response["error"],
                    code=500 if "API" in response.get("content", "") else 422,
                    request_id=request_id
                )
            
            # 格式化响应
            formatted_response = self.response_formatter.format_response(
                response=response,
                session_id=session_id,
                request_id=request_id
            )
            
            # 添加时间戳
            formatted_response["timestamp"] = datetime.utcnow().isoformat()
            
            return formatted_response
        
        except Exception as e:
            # 处理所有其他错误
            error_code = 503 if "API" in str(e) or "service" in str(e).lower() else 500
            return self.response_formatter.format_error(
                error_message=str(e),
                request_id=request_id,
                code=error_code
            )
    
    async def process_message_stream(self,
                                   message: str,
                                   session_id: Optional[str] = None,
                                   model_type: Optional[str] = None,
                                   role_name: str = "assistant",
                                   system_prompt: Optional[str] = None,
                                   temperature: float = 0.7) -> AsyncGenerator[str, None]:
        """流式处理用户消息并返回AI回复"""
        # 在方法内部处理默认值
        model_type = os.getenv("DEFAULT_MODEL_TYPE", "deepseek")

        # 生成会话ID
        if not session_id:
            session_id = str(uuid.uuid4())

        try:
            # 获取LLM服务
            llm_service = self.llm_factory.get_llm_service(model_type)
            
            # 获取提示词
            if not system_prompt:
                system_prompt = self.prompt_service.get_system_prompt(role_name)
            
            # 流式生成
            async for chunk in llm_service.generate_stream(
                message=message,
                system_prompt=system_prompt,
                temperature=temperature,
                history=None  # 步骤1不包含历史记录功能
            ):
                # 将字典转换为JSON字符串，并按SSE格式返回
                if isinstance(chunk, dict):
                    yield f"data: {json.dumps(chunk)}\n\n"
                else:
                    # 如果已经是字符串，则直接包装
                    yield f"data: {json.dumps({'content': str(chunk)})}\n\n"
            
        except Exception as e:
            # 错误也需要格式化为SSE
            error_data = {'error': {'message': f"流式生成错误: {str(e)}"}}
            yield f"data: {json.dumps(error_data)}\n\n"

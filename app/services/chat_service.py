import uuid
import os
from typing import Dict, Any, Optional, List, AsyncGenerator
from datetime import datetime
from langchain_core.exceptions import OutputParserException
import json

from .ai.llm.llm_factory import LLMFactory
from .ai.prompt.prompt_service import PromptService
from .ai.response.response_formatter import ResponseFormatter
from .session_service import SessionService
from app.services.ai.llm.role_selector import RoleSelector

class ChatService:
    """聊天服务，整合各个AI组件提供聊天功能"""
    
    def __init__(self, llm_service, session_service, role_selector):
        self.llm_service = llm_service
        self.session_service = session_service
        self.role_selector = role_selector
        self.llm_factory = LLMFactory()
        self.prompt_service = PromptService()
        self.response_formatter = ResponseFormatter()
    
    async def process_message(self, message, session_id, user_id, user_name):
        # 获取会话信息和所有角色
        session = await self.session_service.get_session_by_id(session_id)
        
        # 使用角色选择器选择最相关角色
        selected_role = await self.role_selector.select_most_relevant_role(
            message, session.roles
        )
        
        # 使用选中角色的system_prompt构建完整提示
        prompt = self._build_prompt(message, selected_role)
        
        # 使用LLM生成响应
        response = await self.llm_service.generate_streaming_response(prompt)
        
        return {
            "role": selected_role.role_name,
            "response": response
        }
    
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
            
            # 获取会话和选择角色
            selected_role = None
            if session_id:
                session = await self.session_service.get_session_by_id(session_id)
                if session and session.roles:
                    # 选择最相关角色
                    selected_role = await self.role_selector.select_most_relevant_role(
                        message, session.roles
                    )
                    
                    # 步骤1: 先通知前端已选择的角色
                    if selected_role:
                        selection_notice = {
                            "event": "role_selected",
                            "role_name": selected_role.role_name,
                            "role_id": selected_role.role_id
                        }
                        yield f"data: {json.dumps(selection_notice)}\n\n"
                        
                        # 使用选中角色的system_prompt
                        if selected_role.system_prompt:
                            system_prompt = selected_role.system_prompt
                            role_name = selected_role.role_name
            
            # 如果没有获取到system_prompt，使用默认的
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
                    # 添加选中的角色信息
                    if selected_role and 'content' in chunk:
                        chunk['role_name'] = selected_role.role_name
                    yield f"data: {json.dumps(chunk)}\n\n"
                else:
                    # 如果已经是字符串，则直接包装
                    response_data = {'content': str(chunk)}
                    if selected_role:
                        response_data['role_name'] = selected_role.role_name
                    yield f"data: {json.dumps(response_data)}\n\n"
            
        except Exception as e:
            # 错误也需要格式化为SSE
            error_data = {'error': {'message': f"流式生成错误: {str(e)}"}}
            yield f"data: {json.dumps(error_data)}\n\n"

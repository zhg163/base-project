import uuid
import os
from typing import Dict, Any, Optional, List, AsyncGenerator
from datetime import datetime
from langchain_core.exceptions import OutputParserException
import json
import logging

from .ai.llm.llm_factory import LLMFactory
from .ai.prompt.prompt_service import PromptService
from .ai.response.response_formatter import ResponseFormatter
from .session_service import SessionService
from app.services.ai.llm.role_selector import RoleSelector
from app.services.formatters import StreamFormatter, SSEFormatter
from app.models.entities.mongo_models import Session
from app.services.storage.mongo_service import get_mongo_service
from app.api.deps import get_session_service
from app.services.storage.session_repository import SessionRepository
from app.services.storage.redis_service import RedisService
from app.models.entities.mongo_models import Role
from app.services.storage.mongo_repository import MongoRepository

class ChatService:
    """聊天服务，整合各个AI组件提供聊天功能"""
    
    def __init__(self, llm_service=None, session_service=None, role_selector=None):
        """初始化聊天服务"""
        # 使用注入的依赖，而非尝试自创建
        self.llm_service = llm_service or LLMFactory().get_llm_service()
        self.session_service = session_service  # 必须由外部提供，不自行创建
        self.role_selector = role_selector or RoleSelector(llm_service=self.llm_service)
        
        # 仅创建自身直接负责的对象
        self.stream_formatter = StreamFormatter()
        self.sse_formatter = SSEFormatter()
        
        if not self.session_service:
            # 抛出明确的错误，而不是尝试创建
            raise ValueError("ChatService requires a session_service")
        
        logger = logging.getLogger(__name__)
        logger.info("聊天服务初始化完成")
    
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
        
        # 生成唯一的请求ID作为缓存键
        request_id = f"{session_id}:{uuid.uuid4()}"
        self.sent_content_cache[request_id] = ""
        
        try:
            # 获取LLM服务
            llm_service = LLMFactory().get_llm_service(model_type)
            
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
                system_prompt = PromptService().get_system_prompt(role_name)
            
            # 流式生成
            async for chunk in llm_service.generate_stream(
                message=message,
                system_prompt=system_prompt,
                temperature=temperature,
                history=None  # 步骤1不包含历史记录功能
            ):
                # 处理chunk
                if isinstance(chunk, dict):
                    if 'content' in chunk:
                        # 获取当前完整文本
                        current_text = chunk['content']
                        
                        # 计算新增部分
                        sent_text = self.sent_content_cache.get(request_id, "")
                        new_text = current_text[len(sent_text):]
                        
                        # 更新缓存
                        self.sent_content_cache[request_id] = current_text
                        
                        # 只发送增量部分
                        if new_text:
                            response_data = {'content': new_text}
                            if selected_role:
                                response_data['role_name'] = selected_role.role_name
                            yield f"data: {json.dumps(response_data)}\n\n"
                    else:
                        # 非内容事件直接发送
                        if selected_role:
                            chunk['role_name'] = selected_role.role_name
                        yield f"data: {json.dumps(chunk)}\n\n"
                else:
                    # 字符串类型处理
                    current_text = str(chunk)
                    sent_text = self.sent_content_cache.get(request_id, "")
                    new_text = current_text[len(sent_text):]
                    
                    # 更新缓存
                    self.sent_content_cache[request_id] = current_text
                    
                    # 只发送增量部分
                    if new_text:
                        response_data = {'content': new_text}
                        if selected_role:
                            response_data['role_name'] = selected_role.role_name
                        yield f"data: {json.dumps(response_data)}\n\n"
            
            # 清理缓存
            if request_id in self.sent_content_cache:
                del self.sent_content_cache[request_id]
            
        except Exception as e:
            # 错误也需要格式化为SSE
            error_data = {'error': {'message': f"流式生成错误: {str(e)}"}}
            yield f"data: {json.dumps(error_data)}\n\n"

    async def chat_stream(
        self, 
        session_id: str, 
        message: str, 
        user_id: str = "anonymous",
        show_thinking: bool = False,
        format: str = "sse",
        model_type: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """流式聊天接口，支持情绪事件和不同响应格式"""
        try:
            # 获取会话
            session = await self._get_session(session_id)
            if not session:
                if format == "sse":
                    yield self.sse_formatter.format_sse({"error": "会话不存在"})
                else:
                    yield {"error": "会话不存在"}
                return  # 空返回，只结束函数执行
                
            # 选择角色
            selected_role = None
            if session and session.roles:
                selected_role = await self.role_selector.select_most_relevant_role(
                    message, session.roles
                )
            
            if not selected_role:
                # 使用yield而非return
                if format == "sse":
                    yield self.sse_formatter.format_sse({"error": "无法选择合适的角色"})
                else:
                    yield {"error": "无法选择合适的角色"}
                return  # 空返回，只结束函数执行
            
            role_id = selected_role.role_id
            role_name = selected_role.role_name
            system_prompt = selected_role.system_prompt
            

            
            # 处理流式响应
            if format == "sse":
                # 角色选择事件
                yield self.sse_formatter.role_selected_sse(role_id, role_name)
                
                # 思考过程
                if show_thinking:
                    yield self.sse_formatter.thinking_sse("分析问题...")
                
                # 情绪处理变量
                last_emotion = None
                last_action = None
                
                # 生成响应
                async for result in self.llm_service.generate_stream_with_emotion(message, system_prompt):
                    content = result.get("content", "")
                    emotion = result.get("emotion")
                    action = result.get("action")
                    
                    # 检测到新情绪
                    if emotion and emotion != last_emotion:
                        yield self.sse_formatter.emotion_sse(emotion)
                        last_emotion = emotion
                    
                    # 检测到新动作
                    if action and action != last_action:
                        yield self.sse_formatter.action_sse(action)
                        last_action = action
                    
                    # 发送内容
                    yield self.sse_formatter.content_sse(content, role_name)
                
                # 完成事件
                yield self.sse_formatter.completion_sse()
            else:
                # 普通流式响应
                yield self.stream_formatter.format_role_selection(role_id, role_name)
                
                async for content in self.llm_service.generate_stream(message, system_prompt):
                    yield self.stream_formatter.format_content(content, role_name)
                
                yield self.stream_formatter.format_completion()
            
            # 保存历史记录  待完成
            #await self._save_message_history(session_id, message, "assistant")
            
        except Exception as e:
            logging.error(f"流式聊天出错: {str(e)}")
            if format == "sse":
                yield self.sse_formatter.format_sse({"error": str(e)})
            else:
                yield {"error": str(e)}

    async def _get_session(self, session_id):
        """获取会话信息"""
        try:
            # 使用已初始化的会话服务
            session = await self.session_service.get_session_by_id(session_id)
            return session
        except Exception as e:
            logging.error(f"获取会话失败: {str(e)}")
            return None

    async def chat(self, session_id, message, user_id, show_thinking=False):
        """普通聊天接口（非流式）"""
        try:
            # 获取会话
            session = await self._get_session(session_id)
            if not session:
                return {"error": "会话不存在"}
            
            # 选择角色
            selected_role = None
            if session and session.roles:
                # 使用已注入的角色选择器
                selected_role = await self.role_selector.select_most_relevant_role(
                    message, session.roles
                )
            
            if not selected_role:
                return {"error": "无法选择合适的角色"}
            
            # 获取LLM服务
            llm_service = LLMFactory().get_llm_service()
            
            # 生成回复
            response = await llm_service.generate(
                message=message,
                system_prompt=selected_role.system_prompt,
                temperature=0.7
            )
            
            # 返回结果
            return {
                "role_name": selected_role.role_name,
                "role_id": selected_role.role_id,
                "content": response.get("content", ""),
                "model": response.get("model", "")
            }
            
        except Exception as e:
            logging.error(f"聊天请求处理出错: {str(e)}")
            return {"error": str(e)}

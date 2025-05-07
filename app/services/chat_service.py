import uuid
import os
from typing import Dict, Any, Optional, List, AsyncGenerator
from datetime import datetime
from langchain_core.exceptions import OutputParserException
import json
import logging
import re

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
from app.services.ai.filter.content_filter import ContentFilter
from app.services.ai.rag.rag_router import RAGRouter
from app.services.ai.rag.rag_service import RAGService
from app.services.ai.tools.tool_router import ContentToolRouter
from app.services.ai.tools.function_caller import FunctionCaller

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
        
        # 使用延迟初始化和错误容忍模式初始化新组件
        self.sent_content_cache = {}
        
        try:
            # 确保依赖注入正确
            self.content_filter = ContentFilter()
            self.rag_router = RAGRouter(llm_service=self.llm_service)  # 传入llm_service
            self.rag_service = RAGService()  # 添加RAGService
            self.tool_router = ContentToolRouter()
            self.function_caller = FunctionCaller()
            logger.info("高级功能初始化完成")
        except Exception as e:
            logger.warning(f"高级功能初始化失败，将使用兼容模式: {str(e)}")
            # 设置为None，在使用时需要检查
            self.content_filter = None
            self.rag_router = None
            self.rag_service = None
            self.tool_router = None
            self.function_caller = None
    
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
                        
                        # 更新缓存
                        self.sent_content_cache[request_id] = current_text
                        
                        # 发送完整累积内容，而不是只发送新增部分
                        response_data = {'content': current_text}
                        if selected_role:
                            response_data['role_name'] = selected_role.role_name
                        yield self.sse_formatter.format_sse(response_data)
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
        """流式聊天接口"""
        try:
            # 标记事件是否已发送，避免重复
            events_sent = {
                "role_selected": False,
                "thinking": False
            }
            
            # 初始化情绪和动作变量
            last_emotion = None
            last_action = None
            
            # 1. 获取会话信息
            session = await self._get_session(session_id)
            if not session:
                yield self.sse_formatter.format_sse({'event': 'error', 'message': '会话不存在'})
                return

            # 2. 选择角色
            selected_role = None
            if session and session.roles:
                selected_role = await self.role_selector.select_most_relevant_role(
                    message, session.roles
                )
                
                # 推送角色选择事件 (仅发送一次)
                if selected_role and not events_sent["role_selected"]:
                    selection_notice = {
                        "event": "role_selected",
                        "role_name": selected_role.role_name,
                        "role_id": str(selected_role.id)
                    }
                    yield self.sse_formatter.format_sse(selection_notice)
                    events_sent["role_selected"] = True
            
            # 新增功能: 内容过滤决策
            if self.content_filter:
                try:
                    filter_result = await self.content_filter.filter_content(message)
                    if filter_result["decision"].action == "block":
                        yield self.sse_formatter.format_sse({'event': 'error', 'message': '内容违反规定'})
                        return
                except Exception as e:
                    logging.warning(f"内容过滤失败，继续处理: {str(e)}")
            
            # 3. 发送思考事件 (根据show_thinking参数决定，仅发送一次)
            if show_thinking and not events_sent["thinking"]:
                thinking_event = {"event": "thinking", "message": "分析问题..."}
                yield self.sse_formatter.format_sse(thinking_event)
                events_sent["thinking"] = True
            
            # 新增功能: RAG决策和检索 (提取为单独函数避免代码重复)
            rag_content = await self._get_rag_content(message) if self.rag_router else None
            
            # 4. 确定使用哪个模型 (保持与原接口一致)
            if not model_type:
                model_type = os.getenv("DEFAULT_MODEL_TYPE", "deepseek")
            
            # 获取LLM服务
            llm_service = LLMFactory().get_llm_service(model_type)
            
            # 5. 构建系统提示词
            system_prompt = None
            if selected_role and selected_role.system_prompt:
                system_prompt = selected_role.system_prompt
            else:
                system_prompt = PromptService().get_system_prompt()
            
            # 添加RAG内容到提示词
            if rag_content:
                # 将检索到的知识融入提示词
                system_prompt = self._enrich_prompt_with_rag(system_prompt, rag_content)
            
            # 6. 生成唯一请求ID并初始化缓存
            request_id = f"{session_id}:{uuid.uuid4()}"
            if not hasattr(self, 'sent_content_cache'):
                self.sent_content_cache = {}
            self.sent_content_cache[request_id] = ""
            
            # 7. 生成响应并流式返回
            async for chunk in llm_service.generate_stream(
                message=message,
                system_prompt=system_prompt,
                temperature=0.7,
                rag_content=rag_content,
                filter_decision=filter_result["decision"] if filter_result else None
            ):
                # 处理情绪和动作
                if isinstance(chunk, dict):
                    # 从字典中直接获取emotion和action (如果API直接返回)
                    emotion = chunk.get('emotion')
                    action = chunk.get('action')
                    
                    # 如果没有直接返回情绪和动作，尝试从内容中提取
                    if 'content' in chunk and not emotion:
                        emotion = self._extract_emotion(chunk['content'])
                        logging.debug(f"从内容中提取情绪: {emotion}")
                    
                    if 'content' in chunk and not action:
                        action = self._extract_action(chunk['content'])
                        logging.debug(f"从内容中提取动作: {action}")
                    
                    # 检测到新情绪
                    if emotion and emotion != last_emotion:
                        logging.info(f"发送情绪事件: {emotion}")
                        yield self.sse_formatter.format_sse({
                            "event": "emotion",
                            "emotion": emotion,
                            "role_name": selected_role.role_name if selected_role else None
                        })
                        last_emotion = emotion
                    
                    # 检测到新动作
                    if action and action != last_action:
                        logging.info(f"发送动作事件: {action}")
                        yield self.sse_formatter.format_sse({
                            "event": "action",
                            "action": action,
                            "role_name": selected_role.role_name if selected_role else None
                        })
                        last_action = action
                    
                    # 处理内容
                    if 'content' in chunk:
                        current_text = chunk['content']
                        self.sent_content_cache[request_id] = current_text
                        
                        response_data = {'content': current_text}
                        if selected_role:
                            response_data['role_name'] = selected_role.role_name
                        yield self.sse_formatter.format_sse(response_data)
                
                # 字符串处理
                elif isinstance(chunk, str):
                    current_text = chunk
                    self.sent_content_cache[request_id] = current_text
                    
                    # 从字符串中尝试提取情绪和动作
                    extracted_emotion = self._extract_emotion(current_text)
                    if extracted_emotion and extracted_emotion != last_emotion:
                        logging.info(f"从字符串中提取并发送情绪: {extracted_emotion}")
                        yield self.sse_formatter.format_sse({
                            "event": "emotion",
                            "emotion": extracted_emotion,
                            "role_name": selected_role.role_name if selected_role else None
                        })
                        last_emotion = extracted_emotion
                    
                    extracted_action = self._extract_action(current_text)
                    if extracted_action and extracted_action != last_action:
                        logging.info(f"从字符串中提取并发送动作: {extracted_action}")
                        yield self.sse_formatter.format_sse({
                            "event": "action",
                            "action": extracted_action,
                            "role_name": selected_role.role_name if selected_role else None
                        })
                        last_action = extracted_action
                    
                    # 发送文本内容
                    response_data = {'content': current_text}
                    if selected_role:
                        response_data['role_name'] = selected_role.role_name
                    yield self.sse_formatter.format_sse(response_data)
            
            # 完成事件
            yield self.sse_formatter.format_sse({"event": "completion"})
            
            # 清理缓存
            if request_id in self.sent_content_cache:
                del self.sent_content_cache[request_id]
            
        except Exception as e:
            logging.error(f"流式聊天出错: {str(e)}")
            yield self.sse_formatter.format_sse({'event': 'error', 'message': str(e)})

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

    # 新增辅助方法，提取RAG内容获取逻辑
    async def _get_rag_content(self, message: str) -> Optional[str]:
        """获取RAG内容，提取为单独方法避免重复执行"""
        try:
            rag_decision = await self.rag_router.should_trigger_rag(message)
            if rag_decision.should_trigger and hasattr(self, 'rag_service') and self.rag_service:
                return await self.rag_service.retrieve(message)
        except Exception as e:
            logging.warning(f"RAG路由失败: {str(e)}")
        return None

    # 新增辅助方法，将RAG内容融入提示词
    def _enrich_prompt_with_rag(self, system_prompt: str, rag_content: str) -> str:
        """将RAG内容融入系统提示词"""
        if not rag_content:
            return system_prompt
        
        # 在保持原有提示词结构的情况下添加检索内容
        rag_section = f"\n\n参考知识：\n{rag_content}\n\n请在回答时自然地融入上述参考知识，但不要明确提及你在使用参考资料。"
        
        return system_prompt + rag_section

    def _extract_emotion(self, text: str) -> Optional[str]:
        """从文本中提取情绪标签
        
        示例格式: 『信任』这是一条消息
        """
        # 匹配『情绪』格式
        emotion_pattern = r'『(.*?)』'
        match = re.search(emotion_pattern, text)
        if match:
            emotion = match.group(1)
            logging.info(f"提取到情绪: {emotion}")
            return emotion
        return None

    def _extract_action(self, text: str) -> Optional[str]:
        """从文本中提取动作描述
        
        示例格式: 【微笑】这是一条消息
        """
        # 匹配【动作】格式
        action_pattern = r'【(.*?)】'
        match = re.search(action_pattern, text)
        if match:
            action = match.group(1)
            logging.info(f"提取到动作: {action}")
            return action
        return None

# app/services/ai/prompt/prompt_service.py
from typing import List, Dict, Any, Optional
import json
from app.services.storage.redis_service import RedisService
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.prompts.chat import SystemMessagePromptTemplate, HumanMessagePromptTemplate
from app.core.config import settings
from app.models.schemas.role import RoleResponse
from app.models.schemas.message import Message
from app.services.storage.mongo_repository import MongoRepository
from app.services.ai.memory.memory_service import MemoryService
from app.utils.logging import logger


class PromptService:
    """提示词服务，管理模板和生成提示"""
    
    def __init__(
        self, 
        redis_service: RedisService = None, 
        role_repo: MongoRepository = None,
        memory_service: MemoryService = None
    ):
        self.redis = redis_service or RedisService()
        self.role_repo = role_repo
        self.memory_service = memory_service
    
    async def get_role(self, role_id: str) -> Optional[RoleResponse]:
        """获取角色信息，优先从Redis缓存获取"""
        role_key = f"role:{role_id}"
        role_data = await self.redis.get(role_key)
        
        if role_data:
            try:
                role_dict = json.loads(role_data)
                return RoleResponse(**role_dict)
            except Exception as e:
                logger.error(f"解析角色数据失败: {e}")
        
        # 降级到MongoDB
        if self.role_repo:
            role = await self.role_repo.get(role_id)
            if role:
                # 更新Redis缓存
                role_dict = role.model_dump()
                await self.redis.set(
                    role_key, 
                    json.dumps(role_dict),
                    ex=3600  # 缓存1小时
                )
                return RoleResponse(**role_dict)
        
        return None
    
    def create_prompt_template(self, role: RoleResponse) -> ChatPromptTemplate:
        """根据角色创建高级提示词模板"""
        # 基础系统提示词
        system_template = role.system_prompt or "你是一个有帮助的助手。"
        
        # 添加角色特性区块
        if role.personality:
            system_template += f"\n\n【角色特性】\n{role.personality}"
        
        if role.speech_style:
            system_template += f"\n\n【语言风格】\n{role.speech_style}"
        
        # 添加行为指导区块
        system_template += "\n\n【表达指南】"
        system_template += "\n- 情感表达: 当你想表达情感时，请使用[情感:喜悦]这样的格式。"
        system_template += "\n- 动作描述: 当你想描述动作时，请使用[动作:思考]这样的格式。"
        
        # 添加知识区块（为RAG预留）
        system_template += "\n\n【参考知识】\n{context}"
        
        # 添加行为规则区块
        system_template += "\n\n【行为规则】"
        system_template += "\n- 敏感内容: 拒绝讨论政治敏感、暴力、色情等不适当内容。"
        system_template += "\n- 日常回复: 保持友好、耐心的态度回答用户问题。"
        
        # 创建LangChain模板，增加context占位符
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_template),
            MessagesPlaceholder(variable_name="history"),  # 历史消息占位符
            HumanMessagePromptTemplate.from_template("{input}")  # 当前输入占位符
        ])
    
    def format_history(self, messages: List[Message]) -> List[Dict[str, str]]:
        """将消息历史转换为LangChain格式"""
        formatted_history = []
        
        for msg in messages:
            if msg.role == "user":
                formatted_history.append({"type": "human", "content": msg.content})
            elif msg.role == "assistant":
                formatted_history.append({"type": "ai", "content": msg.content})
            elif msg.role == "system":
                formatted_history.append({"type": "system", "content": msg.content})
                
        return formatted_history
    async def format_history_with_memory(
        self, 
        session_id: str, 
        recent_messages: List[Message] = None
    ) -> List[Dict[str, str]]:
        """结合内存服务获取格式化的历史记录"""
        # 如果提供了recent_messages则使用，否则从memory_service获取
        if recent_messages:
            return self.format_history(recent_messages)
            
        if self.memory_service:
            # 从记忆服务获取历史
            history = await self.memory_service.get_chat_history(session_id)
            return self.format_history(history)
        
        return []
    async def generate_prompt(
        self, 
        role_id: str, 
        session_id: str,
        input_text: str,
        temperature: float = None,
        context: str = None,
        recent_messages: List[Message] = None
    ) -> Optional[Dict[str, Any]]:
        """生成完整提示，包含记忆集成"""
        # 获取角色
        role = await self.get_role(role_id)
        if not role:
            logger.error(f"角色未找到: {role_id}")
            return None
        
        # 创建提示词模板
        prompt_template = self.create_prompt_template(role)
        
        # 格式化历史记录
        formatted_history = await self.format_history_with_memory(
            session_id, recent_messages
        )
        
        try:
            # 组装提示参数
            prompt_args = {
                "history": formatted_history,
                "input": input_text,
                "context": context or ""  # 为RAG预留的上下文
            }
            
            # 生成完整提示
            prompt_dict = prompt_template.format_prompt(**prompt_args).to_messages()
            
            # 设置温度参数
            temp = temperature or role.temperature or 0.7
            
            return {
                "messages": prompt_dict,
                "temperature": temp,
                "model": settings.DEFAULT_LLM_MODEL
            }
        except Exception as e:
            logger.error(f"生成提示词失败: {e}", exc_info=True)
            return None
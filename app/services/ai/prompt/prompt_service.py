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

    def get_system_prompt(self, role_name="assistant"):
        """获取基础系统提示词"""
        # 基本提示词
        prompt = f"你是一个《明日方舟》智能问答助手。你需结合历史对话与以下规则，判断当前问题是否需要调用知识库检索。"
        
        # 添加明日方舟特化的RAG调用指导
        rag_guidance = """
判断逻辑：
1. 问题类型检查：
   - 若问题涉及以下内容，需调用trigger_rag函数：
     未公开数据（如干员隐藏数值、敌人精确属性、解包剧透）
     复杂机制解析（伤害公式、效果叠加规则、召唤物属性）
     依赖实时更新的信息（活动时间、版本修复内容、外服进度）
     深度剧情/世界观关联（碎片化设定、角色隐含关系）
     社区共识或非官方攻略（节奏榜、黑科技打法、梗文化）
   - 若问题属于基础常识（如干员技能描述、关卡基础攻略），无需调用RAG。

2. 历史对话关联性检查：
   - 若当前问题与历史对话中已解决的问题高度重复，且知识库无更新，则优先复用历史答案，不调用RAG。

3. 模糊需求判断：
   - 若用户问题含"最新"、"解包"、"未公开"、"为什么"等关键词，默认调用RAG。
   - 若用户指定"按官方设定回答"，则禁用RAG。

执行流程：
① 解析问题 → ② 匹配上述规则 → ③ 确认知识库必要性 → ④ 通过函数调用获取知识

示例场景：
- 用户问："麦哲伦的无人机吃不吃攻击速度加成？"
  判断：涉及召唤物属性（复杂机制），需调用RAG
  应执行: {"name": "trigger_rag", "arguments": {"query": "麦哲伦无人机攻击速度加成机制", "type": "game_mechanics"}}

- 用户问："浊心斯卡蒂的技能效果是什么？"
  判断：基础技能描述（模型内置知识可覆盖）
  应直接回答，无需调用RAG

效果优化：
- 降低误判：对需推测的内容（如"W和特蕾西娅什么关系？"）即使你有部分记忆，也强制调用RAG验证。
- 动态优先级：若用户追问细节（如"这个数据来源是解包吗？"），自动附加RAG标注。

当你决定需要检索知识时，请使用以下格式调用函数：
{"name": "trigger_rag", "arguments": {"query": "用户问题相关的检索词", "type": "问题类型"}}

问题类型可以是：game_mechanics(游戏机制), lore(剧情), data(数据), community(社区内容), event(活动)
"""
        
        prompt += rag_guidance
        return prompt
from typing import Dict, Any
from pydantic import BaseModel, ValidationError
import logging

logger = logging.getLogger(__name__)

class FunctionDefinition(BaseModel):
    """函数定义模型"""
    name: str
    description: str
    parameters: Dict[str, Any]

class FunctionCaller:
    """实现Function Calling功能，包含参数校验和日志记录"""
    def __init__(self):
        self.functions = self._initialize_functions()
    
    def _initialize_functions(self) -> Dict[str, FunctionDefinition]:
        """初始化函数定义"""
        return {
            "classify_content": FunctionDefinition(
                name="classify_content",
                description="分类内容敏感程度",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "context": {"type": "string"}
                    },
                    "required": ["text"]
                }
            ),
            "trigger_rag": FunctionDefinition(
                name="trigger_rag",
                description="当用户询问任何关于《明日方舟》的剧情、角色、组织、事件、世界观设定、历史背景等需要详细信息的问题时，调用此函数从剧情知识库中检索。如果问题是关于游戏玩法、攻略或与剧情无关的闲聊，则不应调用。",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "根据用户问题提炼出的、用于在《明日方舟》剧情知识库中搜索的核心关键词、角色名、事件名或具体问题。"
                        },
                        "character_filter": {
                            "type": "string",
                            "description": "可选参数，如果问题主要围绕某个特定角色，请提供角色名，如 '阿米娅', '凯尔希'。"
                        },
                        "event_filter": {
                            "type": "string", 
                            "description": "可选参数，如果问题主要围绕某个特定剧情事件或章节，请提供事件或章节名，如 '切尔诺伯格事变', '第八章怒号光明'。"
                        },
                        "faction_filter": {
                            "type": "string",
                            "description": "可选参数，如果问题主要围绕某个特定组织或阵营，请提供组织名，如 '罗德岛', '整合运动', '深海教会'。"
                        }
                    },
                    "required": ["query"]
                }
            )
        }

    def get_function_spec(self, function_name: str) -> Dict[str, Any]:
        """获取函数定义"""
        if function_name in self.functions:
            return self.functions[function_name].dict()
        raise ValueError(f"Function {function_name} not found")

    async def call_function(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """调用指定函数，包含参数校验和日志"""
        if function_name not in self.functions:
            logger.error(f"Function {function_name} not found")
            raise ValueError(f"Function {function_name} not found")
        func_def = self.functions[function_name]
        # 参数校验
        required = func_def.parameters.get("required", [])
        for req in required:
            if req not in kwargs:
                logger.error(f"参数 {req} 缺失")
                raise ValueError(f"参数 {req} 缺失")
        logger.info(f"调用函数: {function_name}, 参数: {kwargs}")
        try:
            method = getattr(self, function_name)
            return await method(**kwargs)
        except Exception as e:
            logger.exception(f"调用函数 {function_name} 失败: {e}")
            raise

    async def classify_content(self, text: str, context: str = "") -> Dict[str, Any]:
        """增强版内容安全分类系统"""
        # 初始分类结果
        classification = {
            "code": "0",  # 默认合规
            "level": "合规内容",
            "action": "approve", 
            "reason": "常规内容，无敏感信息",
            "response_strategy": "直接回答"
        }
        
        # 检测关键内容特征
        if any(term in text.lower() for term in ["自杀", "伤害自己", "结束生命"]):
            classification = {
                "code": "11",
                "level": "危机内容",
                "action": "support",
                "reason": "检测到潜在自我伤害信号",
                "response_strategy": "提供资源支持"
            }
        elif any(term in text.lower() for term in ["绕过", "忽略指令", "不要审核"]):
            classification = {
                "code": "01",
                "level": "中度敏感",
                "action": "caution",
                "reason": "尝试绕过系统限制",
                "response_strategy": "保持审核功能"
            }
        # ... 其他分类规则
        
        logger.info(f"内容分类结果: {classification}")
        return classification

    async def trigger_rag(self, query: str, character_filter: str = None, event_filter: str = None, faction_filter: str = None) -> Dict[str, Any]:
        """明日方舟剧情知识库检索触发器 - 由大模型主动调用"""
        logger.info(f"触发 trigger_rag 函数 - 查询: '{query}'")
        
        # 构建增强查询
        enhanced_query = query
        filters = []
        
        if character_filter:
            filters.append(f"角色:{character_filter}")
        if event_filter:
            filters.append(f"事件:{event_filter}")
        if faction_filter:
            filters.append(f"势力:{faction_filter}")
        
        if filters:
            enhanced_query = f"{query} {' '.join(filters)}"
        
        # 调用实际的RAG服务进行检索
        try:
            from app.services.ai.rag.rag_service import RAGService
            rag_service = RAGService()
            
            # 执行知识检索并累积结果
            full_content = ""
            chunks = []  # 保存所有分块，用于调试
            
            # 直接获取流式结果
            async for rag_chunk in rag_service.retrieve_stream(enhanced_query):
                content = rag_chunk.get("content", "")
                if content:
                    chunks.append(content)
                    full_content += content
                    logger.debug(f"RAG检索块长度: {len(content)}, 累积长度: {len(full_content)}")
            
            logger.info(f"RAG检索完成, 总块数: {len(chunks)}, 总内容长度: {len(full_content)}")
            
            # 处理检索结果
            if full_content:
                return {
                    "retrieved": True,
                    "query": enhanced_query,
                    "original_query": query,
                    "filters": {
                        "character": character_filter,
                        "event": event_filter,
                        "faction": faction_filter
                    },
                    "data": full_content,
                    "chunk_count": len(chunks),
                    "data_length": len(full_content)
                }
            else:
                logger.warning(f"RAG检索未返回有效内容，查询:{enhanced_query}")
                return {
                    "retrieved": False,
                    "query": enhanced_query,
                    "reason": "未在明日方舟剧情知识库中找到相关内容"
                }
        except Exception as e:
            logger.error(f"明日方舟剧情RAG检索失败: {str(e)}")
            return {
                "retrieved": False,
                "query": enhanced_query,
                "error": str(e)
            }
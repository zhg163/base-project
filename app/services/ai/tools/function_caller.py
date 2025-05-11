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
                description="触发知识检索",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "type": {"type": "string"}
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

    async def trigger_rag(self, query: str, type: str = "default") -> Dict[str, Any]:
        """知识检索触发器 - 由大模型主动调用"""
        logger.info(f"大模型触发RAG检索: 查询={query}, 类型={type}")
        
        # 调用实际的RAG服务进行检索
        try:
            from app.services.ai.rag.rag_service import RAGService
            rag_service = RAGService()
            
            # 执行知识检索
            retrieved_content = await rag_service.retrieve(query)
            
            # 处理检索结果
            if retrieved_content:
                return {
                    "retrieved": True,
                    "query": query,
                    "type": type,
                    "data": retrieved_content
                }
            else:
                return {
                    "retrieved": False,
                    "query": query,
                    "reason": "未找到相关知识"
                }
        except Exception as e:
            logger.error(f"RAG检索失败: {str(e)}")
            return {
                "retrieved": False,
                "query": query,
                "error": str(e)
            }
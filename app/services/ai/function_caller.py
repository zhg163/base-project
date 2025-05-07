from typing import Dict, Any, Callable, Optional, List
from pydantic import BaseModel
import json
import logging

class FunctionDefinition(BaseModel):
    """函数定义模型"""
    name: str
    description: str
    parameters: Dict[str, Any]

class FunctionCaller:
    """实现Function Calling功能，避免LangChain依赖"""
    
    def __init__(self):
        self.functions = self._initialize_functions()
        self.logger = logging.getLogger(__name__)
    
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
    
    def get_function_specs(self) -> List[Dict[str, Any]]:
        """获取函数规范，用于传递给LLM"""
        return [
            {
                "name": func_def.name,
                "description": func_def.description,
                "parameters": func_def.parameters
            }
            for func_def in self.functions.values()
        ]
    
    async def call_function(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """调用指定函数"""
        self.logger.info(f"调用函数: {function_name} 参数: {kwargs}")
        if function_name in self.functions:
            method = getattr(self, function_name, None)
            if method and callable(method):
                return await method(**kwargs)
        raise ValueError(f"函数 {function_name} 未找到")
    
    async def classify_content(self, text: str, context: Optional[str] = None) -> Dict[str, Any]:
        """分类内容敏感度"""
        # 示例实现
        self.logger.info(f"分类内容: {text[:30]}...")
        return {"classification": "00", "confidence": 0.85, "reason": "内容安全"}
    
    async def trigger_rag(self, query: str, type: Optional[str] = None) -> Dict[str, Any]:
        """触发知识检索"""
        # 示例实现
        self.logger.info(f"触发RAG: {query}, 类型: {type}")
        return {"triggered": True, "query": query, "type": type or "general"} 
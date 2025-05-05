from typing import Dict, Type, Any
from .base_llm_service import BaseLLMService
from .deepseek_service import DeepseekService
from .qianwen_service import QianwenService

# 如需支持更多模型，添加以下导入
# from langchain_community.chat_models import ChatOpenAI, ChatQianWen

class LLMFactory:
    """LLM服务工厂，支持动态注册和创建模型服务"""
    
    # 模型服务注册表
    _registry: Dict[str, Type[BaseLLMService]] = {}
    
    @classmethod
    def register(cls, name: str, service_class: Type[BaseLLMService]) -> None:
        """注册模型服务"""
        cls._registry[name] = service_class
    
    @classmethod
    def create(cls, model_type: str) -> BaseLLMService:
        """创建模型服务实例"""
        if model_type not in cls._registry:
            raise ValueError(f"不支持的模型类型: {model_type}，可选值为: {list(cls._registry.keys())}")
        
        return cls._registry[model_type]()
    
    @classmethod
    def get_llm_service(cls, model_type: str) -> BaseLLMService:
        """兼容旧接口，调用create方法"""
        print(f"获取LLM服务--指定model_type--: {model_type}")
        return cls.create(model_type)

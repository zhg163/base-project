from typing import Dict, Type, Any
from .base_llm_service import BaseLLMService
from .deepseek_service import DeepseekService
from .qianwen_service import QianwenService
import os

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

    def get_llm_service(self, model_type=None):
        """获取LLM服务实例
        
        Args:
            model_type: 可选的模型类型，如果为None则使用环境变量配置
        """
        model_type = model_type or os.getenv("DEFAULT_MODEL_TYPE", "deepseek")
        
        if model_type == "qianwen":
            return self._get_qianwen_service()
        elif model_type == "deepseek":
            return self._get_deepseek_service()
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")
    
    # 使用下划线前缀表示这是私有辅助方法
    def _get_deepseek_service(self):
        """获取DeepSeek服务（惰性加载）"""
        if not hasattr(self, '_deepseek_service'):
            from app.services.ai.llm.deepseek_service import DeepseekService
            self._deepseek_service = DeepseekService()
        return self._deepseek_service

    def _get_qianwen_service(self):
        """获取Qianwen服务实例"""
        if not hasattr(self, '_qianwen_service'):
            from app.services.ai.llm.qianwen_service import QianwenService
            self._qianwen_service = QianwenService()
        return self._qianwen_service

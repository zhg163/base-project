from app.services.ai.llm.llm_factory import LLMFactory
from app.services.ai.llm.deepseek_service import DeepseekService
from app.services.ai.llm.qianwen_service import QianwenService

def initialize_services():
    """初始化服务和注册模型"""
    # 注册LLM服务
    LLMFactory.register("deepseek", DeepseekService)
    LLMFactory.register("qianwen", QianwenService)
    
    # 可以在这里注册其他服务...

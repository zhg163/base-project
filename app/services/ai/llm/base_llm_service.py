from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, AsyncGenerator, List
import re

class BaseLLMService(ABC):
    """LLM服务抽象基类 - 定义所有模型必须实现的接口"""
    
    @abstractmethod
    def initialize(self) -> None:
        """初始化服务配置"""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """返回模型名称"""
        pass
    
    @abstractmethod
    async def generate(
        self, 
        message: str,  # 统一使用message作为参数名
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[Any, Any]:
        """生成回复的标准接口"""
        pass
    
    @abstractmethod
    async def generate_stream(
        self, 
        message: str,  # 统一使用message作为参数名 
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式生成回复的标准接口"""
        pass

    @abstractmethod
    async def generate_stream_with_emotion(self, message, system_prompt, **kwargs):
        """带情绪检测的流式生成"""
        pass

    def extract_emotion(self, text):
        """从文本中提取情绪标签"""
        emotion_pattern = r'『([\w]+)』'
        match = re.search(emotion_pattern, text)
        if match:
            return match.group(1)
        return None

import os
import logging
from typing import Dict, Any, Optional, AsyncGenerator, List
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, SystemMessage
from dashscope import Generation
from dashscope.api_entities.dashscope_response import DashScopeAPIResponse

from app.services.ai.llm.base_llm_service import BaseLLMService

load_dotenv()
logger = logging.getLogger(__name__)

class QianwenService(BaseLLMService):
    """千问模型服务实现"""
    
    def __init__(self):
        """初始化千问服务"""
        # 加载环境变量中的API密钥
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self._model_name = os.getenv("QIANWEN_MODEL_NAME", "qwen-max")
        
        # 验证API密钥
        if not self.api_key:
            logger.warning("未设置DASHSCOPE_API_KEY环境变量")
        else:
            logger.info(f"千问服务初始化完成，使用模型: {self._model_name}")
        
        # 开发模式
        self.dev_mode = os.getenv("DEV_MODE", "False").lower() == "true"
        logger.info(f"开发模式状态: {self.dev_mode}")
        
        # 调用初始化方法
        self.initialize()
    
    def initialize(self):
        """实现抽象方法：初始化服务配置"""
        # 进行其他必要的初始化
        logger.info("QianwenService 初始化完成")
    
    @property
    def model_name(self) -> str:
        """实现抽象属性/方法：返回模型名称"""
        return self._model_name
    
    async def generate(
        self, 
        message: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[Any, Any]:
        """生成回复"""
        if self.dev_mode:
            return self._generate_dev_response(message)
        
        # 构建请求消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        try:
            # 调用千问API
            response = Generation.call(
                model=self.model_name,
                api_key=self.api_key,
                messages=messages,
                result_format='message',
                temperature=temperature,
                max_tokens=max_tokens or 1024,
                top_p=kwargs.get("top_p", 0.8),
                enable_search=kwargs.get("enable_search", True)
            )
            
            if response.status_code != 200:
                logger.error(f"千问API调用错误: {response.code}, {response.message}")
                return {
                    "error": {
                        "code": response.status_code,
                        "message": f"千问API调用错误: {response.message}"
                    }
                }
            
            # 解析响应
            content = response.output.choices[0].message.content
            return {
                "content": content,
                "model": self.model_name,
                "finish_reason": response.output.choices[0].finish_reason,
                "usage": {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
        except Exception as e:
            logger.exception(f"千问API调用异常: {str(e)}")
            return {
                "error": {
                    "code": 500,
                    "message": f"千问API调用异常: {str(e)}"
                }
            }
    
    async def generate_stream(
        self, 
        message: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式生成回复"""
        if self.dev_mode:
            yield {"content": f"【开发模式】您的问题是：{message}\n\n正在流式生成回复..."}
            yield {"content": "作为一个AI助手，我会尽力提供帮助。"}
            return
            
        # 构建请求消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        try:
            # 调用千问流式API
            response_gen = Generation.call(
                model=self.model_name,
                api_key=self.api_key,
                messages=messages,
                result_format='message',
                temperature=temperature,
                max_tokens=max_tokens or 1024,
                top_p=kwargs.get("top_p", 0.8),
                enable_search=kwargs.get("enable_search", True),
                stream=True  # 启用流式响应
            )
            
            # 处理流式响应
            for response in response_gen:
                if response.status_code != 200:
                    logger.error(f"千问流式API调用错误: {response.code}, {response.message}")
                    yield {
                        "error": {
                            "code": response.status_code,
                            "message": f"千问流式API调用错误: {response.message}"
                        }
                    }
                    return
                
                # 解析每个块的内容
                if response.output and response.output.choices:
                    content = response.output.choices[0].message.content
                    yield {"content": content}
        
        except Exception as e:
            logger.exception(f"千问流式API调用异常: {str(e)}")
            yield {
                "error": {
                    "code": 500,
                    "message": f"千问流式API调用异常: {str(e)}"
                }
            }
    
    def _generate_dev_response(self, message: str) -> Dict[str, Any]:
        """开发模式下生成模拟响应"""
        return {
            "content": f"【千问开发模式】您的问题是：{message}\n\n作为千问AI助手，我会尽力提供帮助。",
            "model": f"{self.model_name}-dev",
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": len(message),
                "completion_tokens": 50,
                "total_tokens": len(message) + 50
            }
        }

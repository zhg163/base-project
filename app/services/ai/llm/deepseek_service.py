import os
import logging
from typing import Dict, Any, Optional, AsyncGenerator, List
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.exceptions import OutputParserException
from dotenv import load_dotenv, find_dotenv
import httpx
import json
import re

# 设置日志记录
logger = logging.getLogger(__name__)

# === 诊断区域1：检查.env文件加载 ===
dotenv_path = find_dotenv(usecwd=True)
logger.info(f"[ENV诊断-1] .env文件路径: {dotenv_path}")
logger.info(f"[ENV诊断-1] .env文件存在: {os.path.exists(dotenv_path)}")

# 读取并打印所有环境变量（除敏感值外）
if os.path.exists(dotenv_path):
    with open(dotenv_path, 'r') as f:
        env_content = f.read().splitlines()
        for line in env_content:
            if line and not line.startswith('#') and '=' in line:
                key = line.split('=')[0]
                # 避免打印完整的密钥值
                logger.info(f"[ENV诊断-1] 发现环境变量: {key}")

# 加载环境变量
load_dotenv_result = load_dotenv(dotenv_path=dotenv_path, override=True)
logger.info(f"[ENV诊断-1] load_dotenv结果: {load_dotenv_result}")

# === 诊断区域2：检查环境变量是否成功加载 ===
api_key_exists = "DEEPSEEK_API_KEY" in os.environ
logger.info(f"[ENV诊断-2] DEEPSEEK_API_KEY环境变量存在: {api_key_exists}")
if api_key_exists:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    logger.info(f"[ENV诊断-2] API密钥长度: {len(api_key)}")
    logger.info(f"[ENV诊断-2] API密钥前4个字符: {api_key[:4] if len(api_key) >= 4 else 'N/A'}")
else:
    logger.error("[ENV诊断-2] DEEPSEEK_API_KEY环境变量未加载!")

from .deepseek_model import DeepSeekChatModel
from .base_llm_service import BaseLLMService
from .model_adapter import ModelAdapter

class DeepseekService(BaseLLMService):
    """DeepSeek模型服务实现"""
    
    def __init__(self):
        """初始化DeepSeek服务"""
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self._model_name = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")
        self.api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
        
        # 验证API密钥
        if not self.api_key:
            logger.warning("未设置DEEPSEEK_API_KEY环境变量")
        else:
            logger.info(f"DeepSeek服务初始化完成，使用模型: {self._model_name}")
        
        # 开发模式
        self.dev_mode = os.getenv("DEV_MODE", "False").lower() == "true"
        logger.info(f"开发模式状态: {self.dev_mode}")
        
        self.initialize()
    
    def initialize(self):
        """实现抽象方法：初始化服务配置"""
        logger.info("DeepseekService 初始化完成")
    
    @property
    def model_name(self) -> str:
        """实现抽象方法：返回模型名称"""
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
        
        # 使用适配器转换参数
        params = ModelAdapter.adapt_to_deepseek(
            message=message,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        # 添加必需的model参数
        params["model"] = self._model_name
        
        try:
            # 调用DeepSeek API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=params,
                    timeout=60.0
                )
            
            response.raise_for_status()
            result = response.json()
            
            # 处理标准化响应
            return {
                "content": result["choices"][0]["message"]["content"],
                "model": self.model_name,
                "finish_reason": result["choices"][0]["finish_reason"],
                "usage": result["usage"]
            }
        except Exception as e:
            logger.error(f"DeepSeek API调用失败: {e}", exc_info=True)
            # 包含请求详情在日志中
            logger.error(f"请求参数: {json.dumps(params)}")
            raise
    
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
            yield {"content": f"【DeepSeek开发模式】您的问题是：{message}\n\n"}
            yield {"content": "正在流式生成回复..."}
            yield {"content": "作为一个AI助手，我会尽力提供帮助。"}
            return
        
        # 使用适配器转换参数
        params = ModelAdapter.adapt_to_deepseek(
            message=message,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        # 添加必需的model参数
        params["model"] = self._model_name
        
        # 添加流式参数
        params["stream"] = True
        
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=params,
                    timeout=60.0
                ) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data:") and not line.startswith("data: [DONE]"):
                            chunk = json.loads(line[5:])
                            if chunk["choices"][0]["delta"].get("content"):
                                yield {"content": chunk["choices"][0]["delta"]["content"]}
        except Exception as e:
            logger.exception(f"DeepSeek流式API调用异常: {str(e)}")
            yield {
                "error": {
                    "code": 500,
                    "message": f"DeepSeek流式API调用异常: {str(e)}"
                }
            }
    
    def _generate_dev_response(self, message: str) -> Dict[str, Any]:
        """开发模式下生成模拟响应"""
        return {
            "content": f"【DeepSeek开发模式】您的问题是：{message}\n\n作为DeepSeek AI助手，我会尽力提供帮助。",
            "model": f"{self.model_name}-dev",
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": len(message),
                "completion_tokens": 50,
                "total_tokens": len(message) + 50
            }
        }

    def extract_emotion(self, text):
        """从文本中提取情绪标签
        示例: 『信任』"博士，这次行动交给你了。"【轻触地图】
        """
        emotion_pattern = r'『([\w]+)』'
        match = re.search(emotion_pattern, text)
        if match:
            return match.group(1)
        return None
        
    def extract_action(self, text):
        """从文本中提取动作描述
        示例: 『信任』"博士，这次行动交给你了。"【轻触地图】
        """
        action_pattern = r'【(.*?)】'
        match = re.search(action_pattern, text)
        if match:
            return match.group(1)
        return None
    
    async def generate_stream_with_emotion(self, message, system_prompt=None, **kwargs):
        """带情绪检测的流式生成"""
        content_buffer = ""
        
        # 处理消息格式
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        async for content_data in self.generate_stream(message, system_prompt, **kwargs):
            # 获取内容
            content = content_data.get("content", "")
            if not content:  # 跳过空内容
                continue
            
            content_buffer += content
            
            # 检查情绪和动作
            emotion = self.extract_emotion(content_buffer)
            action = self.extract_action(content_buffer)
            
            yield {
                "content": content,
                "emotion": emotion,
                "action": action
            }

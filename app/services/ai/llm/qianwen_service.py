import os
import logging
from typing import Dict, Any, Optional, AsyncGenerator, List
from dotenv import load_dotenv
import re
import json

from langchain_core.messages import HumanMessage, SystemMessage
from dashscope import Generation
from dashscope.api_entities.dashscope_response import DashScopeAPIResponse

from app.services.ai.llm.base_llm_service import BaseLLMService
from .model_adapter import ModelAdapter

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
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式生成回复"""
        if self.dev_mode:
            yield {"content": f"【开发模式】您的问题是：{message}\n\n正在流式生成回复..."}
            return
            
        # 使用统一的消息构建方法
        messages = ModelAdapter.build_messages(message, system_prompt, history)
        
        if history:
            logger.info(f"历史消息示例: {history[:1]}")
            #logger.info(f"构建后的完整消息列表: {messages}")
        
        try:
            # 调用千问流式API
            response_gen = Generation.call(
                model=self.model_name,
                api_key=self.api_key,
                messages=messages,  # 使用构建的消息
                result_format='message',
                temperature=temperature,
                max_tokens=kwargs.get("max_tokens", 1024),
                stream=True
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

    async def chat_completion(self, messages: List[Dict[str, str]], **kwargs):
        """修改对话历史格式化方法，确保历史消息被LLM正确处理"""
        logger.info(f"千问模型接收到{len(messages)}条消息")
        
        # 更详细的日志，确保消息被正确处理
        for i, msg in enumerate(messages):
            logger.info(f"原始消息[{i}]详情: role={msg.get('role')}, role_name={msg.get('role_name')}, content长度={len(msg.get('content', ''))}")
        
        # 改进标准化逻辑
        standardized_messages = []
        for msg in messages:
            # 创建新字典而不是复用，避免副作用
            std_msg = {'content': msg.get('content', '')}
            
            # 明确的角色映射规则
            if msg.get('role') == 'assistant' or msg.get('role_name') == 'assistant':
                std_msg['role'] = 'assistant'
            elif msg.get('role') == 'system':
                std_msg['role'] = 'system'
            else:
                std_msg['role'] = 'user'
            
            standardized_messages.append(std_msg)
        
        logger.info(f"标准化后的消息数: {len(standardized_messages)}")
        
        # 确保添加系统提示词，但不要覆盖现有历史
        system_prompt = kwargs.get('system_prompt', '')
        if system_prompt:
            # 添加明确的指令让模型注意历史消息
            memory_instruction = "重要提示：用户之前可能提到过重要信息，请仔细阅读所有历史消息并在回答时准确引用这些信息。"
            system_prompt = memory_instruction + "\n\n" + system_prompt
            kwargs['system_prompt'] = system_prompt
        
        # 确保历史消息被模型重视，在最后一条用户消息前添加提示
        if len(standardized_messages) > 1 and standardized_messages[-1]['role'] == 'user':
            for i in range(len(standardized_messages)-1):
                if standardized_messages[i]['role'] == 'user' and '幸运数字' in standardized_messages[i]['content']:
                    # 让最后一条消息更明确地引用历史
                    standardized_messages[-1]['content'] = f"请记住我之前说过的信息并回答：{standardized_messages[-1]['content']}"
                    break
        
        # 发送前验证消息完整性
        valid_messages = [msg for msg in standardized_messages if msg.get('content') and len(msg.get('content', '')) > 0]
        if len(valid_messages) < len(standardized_messages):
            logger.warning(f"过滤掉了{len(standardized_messages) - len(valid_messages)}条空消息")
            standardized_messages = valid_messages
        
        # 在chat_completion方法的标准化消息后添加
        logger.info(f"最终发送给LLM的完整消息列表: {json.dumps([{{'role': m.get('role'), 'content_preview': m.get('content', '')[:30] + '...' if m.get('content') else ''}} for m in standardized_messages], ensure_ascii=False)}")
        
        # 调用原有实现
        return await self._chat_completion_impl(standardized_messages, **kwargs)

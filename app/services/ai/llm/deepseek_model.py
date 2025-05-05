import os
import json
import logging
from typing import Any, Dict, List, Mapping, Optional, Iterator, AsyncIterator, Union, Literal, ClassVar
import httpx

from langchain_core.callbacks.manager import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ChatMessage, HumanMessage, SystemMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatResult, ChatGenerationChunk
from pydantic.v1 import Field, root_validator

logger = logging.getLogger(__name__)

class DeepSeekChatModel(BaseChatModel):
    """DeepSeek Chat Model集成，实现标准LangChain接口"""
    
    client: Any = None  # 异步HTTP客户端
    model_name: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    stop: Optional[List[str]] = None
    api_base: str = "https://api.deepseek.com"
    api_key: Optional[str] = None
    streaming: bool = False
    
    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """验证API密钥环境变量"""
        values["api_key"] = values["api_key"] or os.getenv("DEEPSEEK_API_KEY")
        # 添加调试日志
        if values["api_key"]:
            logger.info(f"API密钥有效 (前4个字符): {values['api_key'][:4]}...")
        else:
            logger.error("API密钥未配置!")
        
        values["api_base"] = values["api_base"] or os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        return values
    
    def _convert_messages_to_api_format(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """将LangChain消息转换为DeepSeek API需要的格式"""
        api_messages = []
        for message in messages:
            if isinstance(message, SystemMessage):
                api_messages.append({"role": "system", "content": message.content})
            elif isinstance(message, HumanMessage):
                api_messages.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage):
                api_messages.append({"role": "assistant", "content": message.content})
            elif isinstance(message, ChatMessage):
                # 处理通用ChatMessage
                role = message.role
                # DeepSeek支持的角色: system, user, assistant
                if role not in ["system", "user", "assistant"]:
                    logger.warning(f"不支持的消息角色: {role}，将作为user处理")
                    role = "user"
                api_messages.append({"role": role, "content": message.content})
            else:
                logger.warning(f"不支持的消息类型: {type(message)}，将跳过")
        return api_messages
    
    def _create_payload(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """创建API请求的payload"""
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
        }
        
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.top_p is not None:
            payload["top_p"] = self.top_p
        if self.stop is not None:
            payload["stop"] = self.stop
            
        return payload
    
    def _create_chat_result(self, response: Dict[str, Any]) -> ChatResult:
        """从API响应创建ChatResult对象"""
        generation_info = {}
        if "usage" in response:
            generation_info["usage"] = response["usage"]
        
        message = AIMessage(content=response["choices"][0]["message"]["content"])
        
        generation = ChatGeneration(
            message=message,
            generation_info=generation_info
        )
        
        return ChatResult(generations=[generation])
    
    async def _agenerate(
        self, 
        messages: List[BaseMessage], 
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> ChatResult:
        """异步生成聊天响应"""
        if self.client is None:
            self.client = httpx.AsyncClient()
        
        # 转换消息格式
        api_messages = self._convert_messages_to_api_format(messages)
        
        # 创建请求负载
        payload = self._create_payload(api_messages)
        
        # 覆盖参数
        if stop:
            payload["stop"] = payload.get("stop", []) + stop
        
        # 添加其他参数
        payload.update(kwargs)
        
        # 设置请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 构建正确的API端点
        api_endpoint = f"{self.api_base}/v1/chat/completions"
        if self.api_base.endswith("/v1"):
            api_endpoint = f"{self.api_base}/chat/completions"
        
        # 发送API请求
        if not self.streaming:
            try:
                response = await self.client.post(
                    api_endpoint,
                    headers=headers,
                    json=payload,
                    timeout=60.0
                )
                response.raise_for_status()
                data = response.json()
                
                # 回调通知
                if run_manager:
                    await run_manager.on_llm_new_token(
                        data["choices"][0]["message"]["content"]
                    )
                
                return self._create_chat_result(data)
            except Exception as e:
                logger.error(f"DeepSeek API调用错误: {str(e)}")
                raise e
        else:
            # 流式响应处理
            chunks = []
            try:
                async with self.client.stream(
                    "POST",
                    api_endpoint,
                    headers=headers,
                    json={**payload, "stream": True},
                    timeout=60.0
                ) as response:
                    response.raise_for_status()
                    
                    content = ""
                    async for line in response.aiter_lines():
                        if not line.strip() or line.strip() == "data: [DONE]":
                            continue
                        
                        if not line.startswith("data: "):
                            logger.warning(f"收到意外的数据格式: {line}")
                            continue
                            
                        json_data = json.loads(line[6:])
                        delta = json_data.get("choices", [{}])[0].get("delta", {})
                        
                        if "content" in delta and delta["content"]:
                            content += delta["content"]
                            chunks.append(delta["content"])
                            
                            # 回调通知
                            if run_manager:
                                await run_manager.on_llm_new_token(delta["content"])
                    
                    # 创建最终结果
                    final_response = {
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": content
                                },
                                "finish_reason": "stop"
                            }
                        ]
                    }
                    
                    return self._create_chat_result(final_response)
            except Exception as e:
                logger.error(f"DeepSeek 流式API调用错误: {str(e)}")
                raise e
    
    async def _astream(
        self, 
        messages: List[BaseMessage], 
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> AsyncIterator[ChatGenerationChunk]:
        """异步流式生成聊天响应"""
        if self.client is None:
            self.client = httpx.AsyncClient()
        
        # 转换消息格式
        api_messages = self._convert_messages_to_api_format(messages)
        
        # 创建请求负载
        payload = self._create_payload(api_messages)
        payload["stream"] = True
        
        # 覆盖参数
        if stop:
            payload["stop"] = payload.get("stop", []) + stop
        
        # 添加其他参数
        payload.update(kwargs)
        
        # 设置请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            async with self.client.stream(
                "POST",
                f"{self.api_base}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.strip() or line.strip() == "data: [DONE]":
                        continue
                    
                    if not line.startswith("data: "):
                        logger.warning(f"收到意外的数据格式: {line}")
                        continue
                        
                    json_data = json.loads(line[6:])
                    delta = json_data.get("choices", [{}])[0].get("delta", {})
                    
                    if "content" in delta and delta["content"]:
                        chunk = ChatGenerationChunk(
                            message=AIMessageChunk(content=delta["content"])
                        )
                        
                        # 回调通知
                        if run_manager:
                            await run_manager.on_llm_new_token(delta["content"])
                        
                        yield chunk
        except Exception as e:
            logger.error(f"DeepSeek 流式API调用错误: {str(e)}")
            raise e
    
    def _generate(
        self, 
        messages: List[BaseMessage], 
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> ChatResult:
        """同步生成聊天响应（调用异步方法）"""
        import asyncio
        
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(
            self._agenerate(messages, stop, run_manager, **kwargs)
        )
    
    def _llm_type(self) -> str:
        """返回LLM类型，用于序列化"""
        return "deepseek"

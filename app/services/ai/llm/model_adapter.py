from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class ModelAdapter:
    """适配不同模型API的参数转换器"""
    
    @staticmethod
    def adapt_to_deepseek(
        message: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """将统一参数转换为DeepSeek API格式"""
        # DeepSeek特定的参数处理
        return {
            "messages": ModelAdapter.build_messages(message, system_prompt),
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens"),
            # 添加其他DeepSeek特定参数
        }
    
    @staticmethod
    def adapt_to_qianwen(
        message: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """将统一参数转换为千问API格式"""
        # 构建千问特定的参数
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        return {
            "model": kwargs.get("model_name", "qwen-max"),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1024),
            "top_p": kwargs.get("top_p", 0.8),
            "enable_search": kwargs.get("enable_search", True),
        }
    
    @staticmethod
    def build_messages(message: str, system_prompt: Optional[str] = None, history: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
        """
        统一构建消息格式
        
        Args:
            message (str): 当前用户消息
            system_prompt (str, optional): 系统提示词
            history (list, optional): 历史消息列表，每个消息格式为{"role": "xx", "content": "xx"}
            
        Returns:
            list: 格式化的消息列表
        """
        messages = []
        
        # 添加系统提示
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 添加历史消息
        if history and isinstance(history, list):
            # 确保历史消息格式正确
            for msg in history:
                if not isinstance(msg, dict) or "role" not in msg or "content" not in msg:
                    logger.warning(f"跳过格式不正确的历史消息: {msg}")
                    continue
                    
                # 规范化角色名称
                role = msg["role"].lower()
                if role not in ["system", "user", "assistant"]:
                    if role == "bot" or role == "ai":
                        role = "assistant"
                    else:
                        role = "user"
                        
                messages.append({"role": role, "content": msg["content"]})
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": message})
        
        # 记录构建的消息数量
        logger.info(f"构建了{len(messages)}条消息，包含系统提示:{bool(system_prompt)}，历史消息:{len(history) if history else 0}条")
        
        return messages

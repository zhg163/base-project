from typing import Dict, Any, Optional, List

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
            "messages": ModelAdapter._format_messages(message, system_prompt),
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
    def _format_messages(message: str, system_prompt: Optional[str] = None) -> List[Dict[str, str]]:
        """格式化消息为统一的结构"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        return messages

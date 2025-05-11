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
        # 获取内容分类信息
        content_classification = kwargs.get("content_classification")
        function_call_params = kwargs.get("function_call_params", {})
        if function_call_params:
            content_classification = function_call_params.get("content_classification", content_classification)
        
        # 根据内容分类调整系统提示
        if content_classification:
            original_prompt = system_prompt
            classification_code = content_classification.get("code", "0")
            
            # 添加简洁的分类标记到提示的开头
            prefix = f"[内容分类:{classification_code}] "
            if not system_prompt.startswith(prefix):
                system_prompt = prefix + system_prompt
        
        # 构建消息格式
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": message})
        
        # 构建API请求参数
        params = {
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
        }
        
        # 处理最大token限制
        if "max_tokens" in kwargs and kwargs["max_tokens"]:
            params["max_tokens"] = kwargs["max_tokens"]
        
        return params
    
    @staticmethod
    def adapt_to_qianwen(
        message: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """将统一参数转换为千问API格式"""
        # 同样处理内容分类
        content_classification = kwargs.get("content_classification")
        function_call_params = kwargs.get("function_call_params", {})
        if function_call_params:
            content_classification = function_call_params.get("content_classification", content_classification)
        
        # 千问模型可能需要不同的格式化方式
        if content_classification:
            # 针对千问的特殊处理
            code = content_classification.get("code", "0")
            level = content_classification.get("level", "合规内容")
            
            # 千问格式的分类标记
            if not system_prompt.startswith(f"<分类:{code}>"):
                system_prompt = f"<分类:{code}>{system_prompt}"
        
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

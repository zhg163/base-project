from typing import Dict, Any, List, Optional, AsyncGenerator
import logging
import aiohttp
import os
import json
import asyncio

class RAGService:
    """RAG检索服务"""
    
    def __init__(self):
        """初始化RAG服务"""
        self.logger = logging.getLogger(__name__)
        self.api_url = os.getenv("RAGFLOW_API_URL", "http://localhost:9222")
        self.api_key = os.getenv("RAGFLOW_API_KEY", "ragflow-Q3Njg2ODNjMTNjMDExZjBhYTE4MzU1Yz")
        self.chat_id = os.getenv("RAGFLOW_CHAT_ID")  # 可以在实例化时设置
        self.logger.info("RAG服务初始化完成")
    
    async def retrieve(self, query: str, top_k: int = 3) -> Optional[str]:
        """检索相关知识"""
        self.logger.info(f"检索知识: {query[:30]}...")
        
        # 如果没有向量数据库，返回mock数据
        if not self.api_url:
            self.logger.warning("RAGFlow接口未初始化，返回模拟数据")
            
            # 简单的知识模拟
            if "雷姆必拓" in query:
                return """
                雷姆必拓是泰拉大陆西南部的一个国家，以丰富的矿产资源而闻名。
                主要出产源石矿物，但因矿石病危机而导致社会动荡。
                是阿米娅的出生地，也是罗德岛的重要干员来源地之一。
                """
            
            return None
        
        # 实际实现中，这里会连接RAGFlow接口进行检索
        try:
            # 向量检索代码省略
            return "检索到的相关知识..."
        except Exception as e:
            self.logger.error(f"知识检索失败: {str(e)}")
            return None 

    async def retrieve_stream(self, query: str) -> AsyncGenerator[Dict[str, Any], None]:
        """流式检索方法，使用RAGFlow接口返回SSE流"""
        url = f"{self.api_url}/api/v1/chats_openai/{self.chat_id}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": "model",
            "messages": [
                {"role": "system", "content": "你是一个知识库检索助手。请仅使用提供的上下文信息回答问题，不要编造事实。"},
                {"role": "user", "content": query}
            ],
            "stream": True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"RAGFlow请求失败: {response.status} - {error_text}")
                    
                    # 处理SSE流
                    buffer = ""
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if not line or not line.startswith('data:'):
                            continue
                            
                        data_str = line[5:].strip()
                        if data_str == '[DONE]':
                            break
                            
                        try:
                            data = json.loads(data_str)
                            # 提取内容 - 尝试多种可能的路径
                            content = None
                            
                            # OpenAI格式
                            if 'choices' in data and len(data['choices']) > 0:
                                if 'delta' in data['choices'][0]:
                                    content = data['choices'][0]['delta'].get('content', '')
                                elif 'message' in data['choices'][0]:
                                    content = data['choices'][0]['message'].get('content', '')
                            
                            # 直接content字段
                            if not content and 'content' in data:
                                content = data['content']
                                
                            if content:
                                buffer += content
                                yield {
                                    "event": "rag_thinking",
                                    "content": content,
                                    "full_content": buffer
                                }
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            yield {"event": "error", "message": f"RAG检索错误: {str(e)}"} 
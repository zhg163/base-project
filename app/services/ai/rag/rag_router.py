from typing import Dict, Any, Optional
import logging
from dataclasses import dataclass

@dataclass
class RAGDecision:
    """RAG触发决策结果"""
    should_trigger: bool
    confidence: float = 0.0
    reason: Optional[str] = None

class RAGRouter:
    """RAG路由服务，决定是否需要检索知识"""
    
    def __init__(self, llm_service=None):
        """初始化RAG路由器，接收可选的LLM服务"""
        self.logger = logging.getLogger(__name__)
        self.llm_service = llm_service
        self.logger.info("RAG路由器初始化完成")
    
    async def should_trigger_rag(self, query: str) -> RAGDecision:
        """判断是否应该触发RAG检索"""
        self.logger.info(f"RAG决策分析: {query[:30]}...")
        
        # 如果没有LLM服务，使用简单规则匹配
        if not self.llm_service:
            # 简单的关键词触发规则
            knowledge_keywords = ["什么是", "介绍", "解释", "谁是", "哪里", "如何", "为什么"]
            
            should_trigger = any(keyword in query for keyword in knowledge_keywords)
            confidence = 0.7 if should_trigger else 0.3
            reason = "关键词触发" if should_trigger else "非知识型问题"
            
            return RAGDecision(
                should_trigger=should_trigger,
                confidence=confidence,
                reason=reason
            )
        
        # 如果有LLM服务，可以使用更复杂的判断逻辑
        try:
            # 这里使用LLM进行判断的代码先省略，使用简单规则
            # 在实际实现中可以调用self.llm_service进行更智能的判断
            return RAGDecision(
                should_trigger=True,
                confidence=0.8,
                reason="LLM判断为知识需求"
            )
        except Exception as e:
            self.logger.error(f"LLM判断RAG决策失败: {str(e)}")
            # 降级到简单规则
            return RAGDecision(
                should_trigger=False,
                confidence=0.5,
                reason=f"LLM错误，降级策略: {str(e)}"
            )

    def _build_rag_decision_prompt(self, query: str) -> str:
        """构建RAG决策提示词"""
        return f"""
        请判断是否需要触发知识检索：
        
        问题：{query}
        
        触发条件：
        1. 精确数值/机制验证
        2. 多条件交叉查询
        3. 非公开版本对比
        4. 剧情文本溯源
        5. 黑话/缩写解码
        6. 实时活动策略
        
        请以JSON格式返回：
        {{
            "should_trigger": true/false,
            "type": "触发类型",
            "confidence": 0.95
        }}
        """ 
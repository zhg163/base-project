from typing import Dict, Any
import logging
from .models import FilterDecision

class SensitiveClassifier:
    """敏感内容分类器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("敏感内容分类器初始化")
    
    async def classify(self, text: str) -> Dict[str, Any]:
        """分类内容的敏感程度"""
        # 简单实现，可以在后续开发中完善
        sensitive_words = ["违规", "敏感", "攻击", "歧视"]
        
        # 检查是否包含敏感词
        contains_sensitive = any(word in text for word in sensitive_words)
        
        if contains_sensitive:
            return {
                "decision": FilterDecision(action="warn", reason="包含潜在敏感词"),
                "confidence": 0.7,
                "matched_words": [word for word in sensitive_words if word in text]
            }
        
        return {
            "decision": FilterDecision(action="pass"),
            "confidence": 0.9,
            "reason": "内容安全"
        } 
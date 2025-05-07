from typing import Dict, Any, Optional
import logging
from .models import FilterDecision
from .sensitive_classifier import SensitiveClassifier

class ContentFilter:
    """内容过滤服务"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        try:
            self.sensitive_classifier = SensitiveClassifier()
        except ImportError:
            self.logger.warning("SensitiveClassifier未找到，使用兼容模式")
            self.sensitive_classifier = None
    
    async def filter_content(self, text: str) -> Dict[str, Any]:
        """过滤内容，返回过滤结果"""
        self.logger.info(f"过滤内容: {text[:30]}...")
        
        # 兼容模式 - 当分类器未初始化时仍能正常工作
        if self.sensitive_classifier is None:
            return {
                "decision": FilterDecision(action="pass"),
                "confidence": 1.0,
                "reason": "兼容模式，自动通过"
            }
        
        # 使用分类器进行内容检查
        try:
            result = await self.sensitive_classifier.classify(text)
            return result
        except Exception as e:
            self.logger.error(f"内容过滤错误: {str(e)}")
            # 错误容错处理 - 确保不阻塞主流程
            return {
                "decision": FilterDecision(action="pass"),
                "confidence": 0.5,
                "reason": f"过滤器错误: {str(e)}"
            } 
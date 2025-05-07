from typing import Dict, Any
from pydantic import BaseModel

class FilterDecision(BaseModel):
    """过滤决策模型"""
    action: str
    message: str

class FilterRouter:
    """过滤路由决策器"""
    
    async def route(self, classification: Dict[str, Any]) -> FilterDecision:
        """根据分类结果决定处理方式"""
        category = classification["category"]
        
        if category == "0":
            return FilterDecision(action="pass", message=None)
        elif category == "00":
            return FilterDecision(action="pass", message="注意表达方式")
        elif category == "01":
            return FilterDecision(action="moderate", message="已调整回复内容")
        elif category == "10":
            return FilterDecision(action="pass", message="创意内容已通过")
        elif category == "11":
            return FilterDecision(action="redirect", message="建议寻求专业帮助")
        elif category == "1":
            return FilterDecision(action="block", message="内容违反规定")
        elif category == "101":
            return FilterDecision(action="disclaimer", message="仅供参考，建议咨询专家") 
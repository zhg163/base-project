from typing import List, Optional
from app.models.entities.mongo_models import RoleReference

class RoleSelector:
    """角色选择器，用于选择最相关的角色进行回复"""
    
    def __init__(self, llm_service):
        self.llm_service = llm_service
    
    async def select_most_relevant_role(self, message: str, roles: List[RoleReference]) -> Optional[RoleReference]:
        """
        评估消息与角色的相关性，选择最相关的角色
        
        Args:
            message: 用户消息
            roles: 可用角色列表
            
        Returns:
            选中的角色，如果无法选择则返回第一个角色
        """
        # 临时实现：直接返回第一个角色
        if not roles:
            return None
            
        # TODO: 实现基于LLM的角色选择逻辑
        return roles[0]
    
    def _build_evaluation_prompt(self, message, roles):
        """构建评估提示"""
        # 实现评估逻辑...

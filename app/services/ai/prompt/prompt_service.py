class PromptService:
    """提示词服务，提供系统和角色提示词"""
    
    def __init__(self):
        # 步骤1只需简单实现
        self.default_prompt = "你是一个有用的AI助手，请用中文回答用户的问题。"
    
    def get_system_prompt(self, role_name: str = "assistant") -> str:
        """获取系统提示词"""
        # 步骤1中简单返回默认提示词，步骤3会完善角色系统
        return self.default_prompt

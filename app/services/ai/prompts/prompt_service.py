async def get_system_prompt(self, role_id: str = None, role_name: str = None):
    """获取角色的系统提示"""
    # 获取系统提示的逻辑
    # ...
    
    logger.info(f"获取角色系统提示: role_id={role_id}, role_name={role_name}")
    
    if role_prompt:
        # 增加记忆增强指令
        enhanced_prompt = role_prompt + "\n\n请记住我们的对话历史，包括之前提到的重要信息。"
        logger.info(f"增强后的系统提示长度: {len(enhanced_prompt)}")
        logger.info(f"系统提示开头: {enhanced_prompt[:100]}...")
        return enhanced_prompt
    else:
        logger.warning(f"未找到角色系统提示: role_id={role_id}, role_name={role_name}")
        return DEFAULT_PROMPT 
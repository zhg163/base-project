class StreamFormatter:
    """流式响应格式化器，负责生成标准的流式响应格式"""
    
    def format_role_selection(self, role_id, role_name):
        """生成角色选择事件"""
        return {
            "event": "role_selected",
            "role_id": role_id,
            "role_name": role_name
        }
    
    def format_thinking(self, content, step_type="thinking"):
        """生成思考步骤事件"""
        return {
            "event": step_type,
            "content": content
        }
    
    def format_content(self, content, role_name):
        """生成内容响应事件"""
        return {
            "content": content,
            "role_name": role_name
        }
    
    def format_completion(self):
        """生成完成事件"""
        return {
            "event": "complete"
        }
    
    def format_emotion(self, emotion, intensity=None, description=None):
        """生成情绪事件"""
        return {
            "event": "emotion",
            "emotion": emotion,
            "intensity": intensity,
            "description": description
        }
    
    def format_action(self, action_text):
        """生成动作事件"""
        return {
            "event": "action",
            "action": action_text
        }

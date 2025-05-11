from .stream_formatter import StreamFormatter
import json

class SSEFormatter:
    """SSE响应格式化器，负责将流式响应转换为SSE格式"""
    
    def __init__(self):
        self.stream_formatter = StreamFormatter()
    
    def format_sse(self, data):
        """将数据格式化为SSE标准格式"""
        if isinstance(data, dict):
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        return f"data: {data}\n\n"
    
    def role_selected_sse(self, role_id, role_name):
        """生成角色选择SSE事件"""
        data = self.stream_formatter.format_role_selection(role_id, role_name)
        return self.format_sse(data)
    
    def thinking_sse(self, content):
        """生成思考步骤SSE事件"""
        data = self.stream_formatter.format_thinking(content)
        return self.format_sse(data)
    
    def content_sse(self, content, role_name):
        """生成内容响应SSE事件"""
        data = self.stream_formatter.format_content(content, role_name)
        return self.format_sse(data)
    
    def emotion_sse(self, emotion, intensity=None, description=None):
        """生成情绪SSE事件"""
        data = self.stream_formatter.format_emotion(emotion, intensity, description)
        return self.format_sse(data)
    
    def action_sse(self, action_text):
        """生成动作SSE事件"""
        data = self.stream_formatter.format_action(action_text)
        return self.format_sse(data)
    
    def completion_sse(self):
        """生成完成SSE事件"""
        data = self.stream_formatter.format_completion()
        return self.format_sse(data)

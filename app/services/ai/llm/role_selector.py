from typing import List, Optional, Dict, Tuple
from app.models.entities.mongo_models import RoleReference
import logging
import re
import json

class RoleSelector:
    """角色选择器，用于选择最相关的角色进行回复"""
    
    def __init__(self, llm_service):
        self.llm_service = llm_service
        self.logger = logging.getLogger(__name__)
        self.last_selected_role = None  # 添加记录上一次选择的角色
    
    async def select_most_relevant_role(self, message: str, roles: List[RoleReference], 
                                        chat_history: List[Dict] = None) -> Optional[RoleReference]:
        """评估消息与角色的相关性，选择最相关的角色"""
        if not roles:
            return None
            
        if len(roles) == 1:
            self.logger.info(f"只有一个角色可选，直接返回: {roles[0].role_name}")
            self.last_selected_role = roles[0]
            return roles[0]
        
        # 检查是否应该沿用上一次对话的角色
        if self.last_selected_role and self._should_continue_with_last_role(message, chat_history):
            # 确保上次的角色在当前可选角色中
            for role in roles:
                if str(role.role_id) == str(self.last_selected_role.role_id):
                    self.logger.info(f"检测到对话连续性，沿用上一次的角色: {role.role_name}")
                    return role
        
        # 构建评估提示
        evaluation_prompt = self._build_evaluation_prompt(message, roles, chat_history)
        
        try:
            # 使用LLM评估最相关角色
            response = await self.llm_service.generate(
                message="",  # 消息内容已在提示中
                system_prompt=evaluation_prompt,
                temperature=0.3  # 低温度保证结果一致性
            )
            
            role_id = self._parse_role_selection(response.get("content", ""), roles)
            selected_role = next((r for r in roles if str(r.role_id) == role_id), None)
            
            if selected_role:
                self.logger.info(f"已选择角色: {selected_role.role_name} (ID: {selected_role.role_id})")
                self.last_selected_role = selected_role  # 更新上一次选择的角色
                return selected_role
            else:
                self.logger.warning(f"无法解析所选角色，返回第一个: {roles[0].role_name}")
                self.last_selected_role = roles[0]  # 更新上一次选择的角色
                return roles[0]
                
        except Exception as e:
            self.logger.error(f"角色选择失败: {str(e)}")
            self.last_selected_role = roles[0]  # 更新上一次选择的角色
            return roles[0]  # 失败时返回第一个角色
    
    def _should_continue_with_last_role(self, message: str, chat_history: List[Dict] = None) -> bool:
        """判断是否应该沿用上一次对话的角色"""
        # 检查是否存在对话历史和上一次选择的角色
        if not chat_history or not self.last_selected_role:
            return False
        
        # 检查消息中是否包含代词"你"、"您"等指代上一个角色的词
        pronoun_pattern = r'(你|您|你们|汝|尔|阁下)'
        if re.search(pronoun_pattern, message):
            return True
            
        # 检查是否是简短的后续问题如"为什么"、"怎么办"、"还有呢"等
        follow_up_pattern = r'^(为什么|怎么办|然后呢|还有呢|继续|详细说说|那么|所以).{0,10}$'
        if re.search(follow_up_pattern, message):
            return True
            
        # 如果最近一次对话是与当前用户的，且时间间隔较短，增加连续性判断
        # 这部分需要根据实际chat_history的结构来实现
            
        return False
    
    def _build_evaluation_prompt(self, message: str, roles: List[RoleReference], history=None) -> str:
        """构建评估提示"""
        # 提取每个角色的专长领域和关键词
        role_descriptions = []
        
        for i, role in enumerate(roles):
            # 提取专业领域
            expertise = self._extract_expertise(role.system_prompt)
            # 提取关键词
            keywords = self._extract_keywords(role.system_prompt)
            
            role_desc = f"角色 {i+1}:\n"
            role_desc += f"ID: {role.role_id}\n"
            role_desc += f"名称: {role.role_name}\n"
            role_desc += f"专长: {expertise}\n"
            role_desc += f"关键词: {keywords}\n"
            role_desc += f"情绪处理: {self._extract_emotions(role.system_prompt)}\n"
            role_descriptions.append(role_desc)
        
        roles_text = "\n\n".join(role_descriptions)
        
        # 添加对话历史上下文（如果有）
        history_context = ""
        if history and len(history) > 0:
            last_messages = history[-3:]  # 获取最近的3条消息
            history_context = "\n## 最近对话历史\n"
            for msg in last_messages:
                role = "用户" if msg.get("role") == "user" else "助手"
                history_context += f"{role}: {msg.get('content', '')}\n"
        
        prompt = f"""你是一个专业的角色选择系统。
根据用户的消息和可用角色列表，选择最适合回答的角色。

## 用户消息
{message}
{history_context}

## 可用角色
{roles_text}

## 选择标准
1. 角色的专业领域与用户问题的相关性
2. 角色设定中的专业知识与用户问题的匹配度
3. 角色性格是否适合回答该类问题
4. 对话连续性：如果用户使用"你"等代词指代上一个对话的角色，应该沿用该角色
5. 如果用户问题是对上一个回答的后续提问，应该使用相同角色回答

## 输出格式
只返回所选角色的ID，无需其他说明。例如: 68171c58e39d5bcf148c742a
"""
        return prompt
    
    def _parse_role_selection(self, response: str, roles: List[RoleReference]) -> str:
        """解析LLM返回的角色选择结果"""
        # 清理响应，寻找角色ID
        cleaned_response = response.strip()
        
        # 验证是否为有效的角色ID
        for role in roles:
            role_id = str(role.role_id)
            if role_id in cleaned_response:
                return role_id
                
        # 如果无法找到匹配的ID，返回第一个角色ID
        return str(roles[0].role_id)

    def _extract_metadata(self, system_prompt: str, field: str) -> str:
        """从system_prompt中提取元数据"""
        try:
            # 匹配<role_metadata>标签中的JSON
            metadata_match = re.search(r'<role_metadata>(.*?)</role_metadata>', 
                                      system_prompt, re.DOTALL)
            
            if metadata_match:
                metadata = json.loads(metadata_match.group(1))
                if field in metadata:
                    # 将列表或字典转为字符串
                    if isinstance(metadata[field], (list, dict)):
                        return json.dumps(metadata[field], ensure_ascii=False)
                    return str(metadata[field])
        except Exception as e:
            self.logger.warning(f"提取元数据失败: {str(e)}")
        
        # fallback: 简单文本分析提取
        return self._legacy_extract(system_prompt, field)

    def _extract_expertise(self, system_prompt: str) -> str:
        return self._extract_metadata(system_prompt, "expertise")

    def _extract_keywords(self, system_prompt: str) -> str:
        return self._extract_metadata(system_prompt, "keywords")

    def _extract_emotions(self, system_prompt: str) -> str:
        return self._extract_metadata(system_prompt, "emotions")

    def _legacy_extract(self, system_prompt: str, field: str) -> str:
        """旧式提取方法，从system_prompt中简单提取字段信息"""
        # 根据不同字段使用不同的提取逻辑
        if field == "expertise":
            # 查找"专长"、"擅长"、"专业"等相关词后的内容
            match = re.search(r'(专长|擅长|专业|领域)\s*[:：]\s*(.*?)(?:\n|$)', system_prompt)
            if match:
                return match.group(2).strip()
        elif field == "keywords":
            # 查找"关键词"、"特点"等相关词后的内容
            match = re.search(r'(关键词|特点|标签)\s*[:：]\s*(.*?)(?:\n|$)', system_prompt)
            if match:
                return match.group(2).strip()
        elif field == "emotions":
            # 查找"情绪"、"情感"等相关词后的内容
            match = re.search(r'(情绪|情感|态度)\s*[:：]\s*(.*?)(?:\n|$)', system_prompt)
            if match:
                return match.group(2).strip()
        
        # 如果没有找到匹配，返回空字符串
        return ""

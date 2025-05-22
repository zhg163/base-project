import uuid
import os
from typing import Dict, Any, Optional, List, AsyncGenerator
from datetime import datetime
from langchain_core.exceptions import OutputParserException
import json
import logging
import re
import asyncio

from .ai.llm.llm_factory import LLMFactory
from .ai.prompt.prompt_service import PromptService
from .ai.response.response_formatter import ResponseFormatter
from .session_service import SessionService
from app.services.ai.llm.role_selector import RoleSelector
from app.services.formatters import StreamFormatter, SSEFormatter
from app.models.entities.mongo_models import Session
from app.services.storage.mongo_service import get_mongo_service
from app.api.deps import get_session_service
from app.services.storage.session_repository import SessionRepository
from app.services.storage.redis_service import RedisService
from app.models.entities.mongo_models import Role
from app.services.storage.mongo_repository import MongoRepository
from app.services.ai.filter.content_filter import ContentFilter
from app.services.ai.rag.rag_router import RAGRouter
from app.services.ai.rag.rag_service import RAGService
from app.services.ai.tools.tool_router import ContentToolRouter
from app.services.ai.tools.function_caller import FunctionCaller
from app.services.ai.memory.memory_service import MemoryService
from app.utils.logging import logger, AILogger, LogContext, merge_extra_data

class ChatService:
    """聊天服务，整合各个AI组件提供聊天功能"""
    
    # 新增：function_call 规范指引
    FUNCTION_CALL_GUIDANCE = '''
当你判断需要调用剧情知识库时，**必须**使用 function_call 结构调用 trigger_rag 工具，而**不能**在 content 字段输出 trigger_rag(...) 相关字符串。

调用规范如下：
- 你必须用如下 JSON 结构输出工具调用：
  {
    "function_call": {
      "name": "trigger_rag",
      "arguments": "{\\\"query\\\": \\\"罗德岛制药 故事\\\"}"
    }
  }
- 不要在 content 字段输出 trigger_rag(...) 字符串或相关内容。
- 只有当你需要直接回复用户时，才在 content 字段输出自然语言内容。

示例：
- 用户问："介绍罗德岛制药的故事"
  - 正确做法：输出 function_call 字段，内容如下：
    {
      "function_call": {
        "name": "trigger_rag",
        "arguments": "{\\\"query\\\": \\\"罗德岛制药 故事\\\"}"
      }
    }
  - 错误做法：在 content 字段输出 trigger_rag(query="罗德岛制药 故事") 或类似内容。

- 用户问："阿米娅有什么背景？"
  - 正确做法：输出
    {
      "function_call": {
        "name": "trigger_rag",
        "arguments": "{\\\"query\\\": \\\"阿米娅 背景\\\", \\\"character_filter\\\": \\\"阿米娅\\\"}"
      }
    }

请严格遵守以上规范。
'''
    
    def __init__(self, llm_service=None, session_service=None, role_selector=None, memory_service=None):
        """初始化聊天服务"""
        # 使用注入的依赖，而非尝试自创建
        self.llm_service = llm_service or LLMFactory().get_llm_service()
        self.session_service = session_service  # 必须由外部提供，不自行创建
        self.role_selector = role_selector or RoleSelector(llm_service=self.llm_service)
        
        # 添加记忆服务
        self.memory_service = memory_service or MemoryService()
        
        # 仅创建自身直接负责的对象
        self.stream_formatter = StreamFormatter()
        self.sse_formatter = SSEFormatter()
        
        if not self.session_service:
            # 抛出明确的错误，而不是尝试创建
            raise ValueError("ChatService requires a session_service")
        
        logger.info("聊天服务初始化完成")
        
        # 使用延迟初始化和错误容忍模式初始化新组件
        self.sent_content_cache = {}
        
        try:
            # 确保依赖注入正确
            self.content_filter = ContentFilter()
            self.rag_router = RAGRouter(llm_service=self.llm_service)  # 传入llm_service
            self.tool_router = ContentToolRouter()
            self.function_caller = FunctionCaller()
            logger.info("高级功能初始化完成")
        except Exception as e:
            logger.warning(f"高级功能初始化失败，将使用兼容模式: {str(e)}")
            # 设置为None，在使用时需要检查
            self.content_filter = None
            self.rag_router = None
            self.tool_router = None
            self.function_caller = None
        
        self._mongo_client = None  # 缓存MongoDB客户端
        
        # 确保只初始化一次RAG服务
        if not hasattr(self, 'rag_service') or not self.rag_service:
            try:
                self.rag_service = RAGService()
                logger.info("RAG服务初始化完成")
            except Exception as e:
                logger.warning(f"RAG服务初始化失败: {str(e)}")
                self.rag_service = None
    

    async def chat_stream(
        self, 
        session_id: str, 
        message: str, 
        user_id: str = "anonymous",
        show_thinking: bool = False,
        format: str = "sse",
        model_type: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """流式聊天接口"""
        with LogContext(session_id=session_id, user_id=user_id) as ctx_logger:
            request_id = f"{session_id}:{uuid.uuid4()}"
            content_buffer = ""  # 用于累积完整回复
            filter_result = None  # 初始化为None
            content_classification = None  # 初始化为None
            ctx_logger.info("进入chat_stream方法")
            try:
                # 标记事件是否已发送，避免重复
                events_sent = {
                    "role_selected": False,
                    "thinking": False
                }
                
                # 情绪和动作变量初始化
                last_emotion = None
                last_action = None
                
                # 1. 获取会话
                session = await self._get_session(session_id)
                if not session:
                    yield self.sse_formatter.format_sse({'event': 'error', 'message': '会话不存在'})
                    return
                
                # 2. 获取历史消息
                history = await self.memory_service.build_message_history(session_id)
                ctx_logger.info("将历史消息添加到LLM上下文", extra={"data": {"message_count": len(history)}})
                
                # 3. 选择角色
                selected_role = None
                if session and session.roles:
                    selected_role = await self.role_selector.select_most_relevant_role(
                        message, 
                        session.roles,
                        chat_history=history  # 添加此参数传递历史消息
                    )
                    
                    # 推送角色选择事件 (仅发送一次)
                    if selected_role and not events_sent["role_selected"]:
                        selection_notice = {
                            "event": "role_selected",
                            "role_name": selected_role.role_name,
                            "role_id": str(selected_role.role_id)
                        }
                        yield self.sse_formatter.format_sse(selection_notice)
                        events_sent["role_selected"] = True
                
                # 4. 保存用户消息
                await self.memory_service.add_user_message(session_id, message, user_id)
                
                # 5. 内容过滤决策
                if self.function_caller:
                    try:
                        # 获取内容分类
                        classification_result = await self.function_caller.call_function(
                            "classify_content", 
                            text=message,
                            context=f"session_id: {session_id}"
                        )
                        
                        # 记录分类结果
                        ctx_logger.info(f"内容分类结果: {classification_result['code']} - {classification_result['level']}")

                        # 根据分类结果决定操作
                        if classification_result["code"] == "1":
                            # 违规内容直接拒绝
                            yield self.sse_formatter.format_sse({
                                'event': 'error', 
                                'message': f'内容违反规定: {classification_result["reason"]}'
                            })
                            return
                        
                        # 将分类结果保存给后续使用
                        content_classification = classification_result
                    except Exception as e:
                        ctx_logger.warning(f"内容分类失败，继续处理: {str(e)}")
                        content_classification = None
                else:
                    # 兼容原有内容过滤方式
                    content_classification = None
                    if self.content_filter:
                        try:
                            filter_result = await self.content_filter.filter_content(message)
                            if filter_result["decision"].action == "block":
                                yield self.sse_formatter.format_sse({'event': 'error', 'message': '内容违反规定'})
                                return
                        except Exception as e:
                            ctx_logger.warning(f"内容过滤失败，继续处理: {str(e)}")
                
                # 6. 发送思考事件 
                if show_thinking and not events_sent["thinking"]:
                    thinking_event = {"event": "thinking", "message": "分析问题..."}
                    yield self.sse_formatter.format_sse(thinking_event)
                    events_sent["thinking"] = True
                
                # 改为初始变量
                rag_content = None  # 初始化为None
                # 后续将通过函数调用由LLM主动触发
                
                # 7. 确定使用哪个模型
                if not model_type:
                    model_type = os.getenv("DEFAULT_MODEL_TYPE", "deepseek")
                
                # 获取LLM服务
                llm_service = LLMFactory().get_llm_service(model_type)
                
                # 8. 构建系统提示词
                # 首先初始化system_prompt为空字符串
                system_prompt = ""
                role_prompt = ""
                # 1. 添加明日方舟RAG指导（第一优先级）
                arknights_rag_guidance = """
[明日方舟剧情知识库功能 - 指令!]
当用户的问题明确包含"介绍"、"故事"、"背景"、"起源"、"历史"、"设定"等词语，并且与《明日方舟》中的角色（如阿米娅、整合运动）、组织（如罗德岛制药）、事件或世界观相关时，你【必须】首先调用名为 `trigger_rag` 的工具来查询剧情知识库。不要尝试使用你自己的知识直接回答这类问题。

例如，当用户问：
- "介绍罗德岛制药的故事" -> 【必须】调用 trigger_rag(query="罗德岛制药 故事")
- "整合运动的起源是什么？" -> 【必须】调用 trigger_rag(query="整合运动 起源")
- "阿米娅有什么背景？" -> 【必须】调用 trigger_rag(query="阿米娅 背景", character_filter="阿米娅")

[明日方舟剧情知识库能力 - 非常重要!]
你拥有一个可以访问《明日方舟》剧情知识库的工具。这个知识库专注于《明日方舟》的叙事内容，包含:
1. 主线剧情：从序章到最新章节的完整故事情节、关键对话、重要转折。
2. 活动剧情：如"SideStory"、"故事集"、"插曲"等限时或常驻活动的剧情内容。
3. 角色背景：干员的个人档案、语音中揭示的背景故事、与其他角色的关系、经历和动机。
4. 世界观设定：泰拉世界的地理、国家、种族、历史事件、源石病、天灾、移动城市等核心设定。
5. 组织势力：罗德岛制药、整合运动、各国政府、商业联合会、宗教团体等的背景、目标和行动。
6. 专有名词解释：游戏中出现的特定术语、物品、概念的剧情含义。

[明日方舟剧情知识库使用指南]
应该调用剧情知识库的情况：
• 用户询问特定角色背景、个性或经历。
• 用户询问特定剧情事件细节。
• 用户想了解某个国家、组织或种族的背景。
• 用户对世界观设定有疑问。
• 用户的问题需要深入档案、对话或剧情文本的精确信息。
• 用户想回顾或理清某段剧情脉络。

不应该调用剧情知识库的情况：
• 关于游戏玩法机制的问题。
• 关于游戏更新、开发商等游戏外信息的问题。
• 寻求抽卡建议或干员强度排行的问题。
• 闲聊、问候或与《明日方舟》剧情无关的内容。
• 非常模糊，无法形成有效搜索查询的问题。

当用户问题涉及明日方舟剧情但你没有把握准确回答时，请务必调用剧情知识库获取准确信息。
"""

                # 1.将明日方舟RAG指导添加到system_prompt（如果相关）
                system_prompt += self.FUNCTION_CALL_GUIDANCE + "\n" + arknights_rag_guidance
                
                # 2. 添加内容分类信息（第二优先级）
                if content_classification:
                    response_guidance = f"""
内容分类: {content_classification['code']} ({content_classification['level']})
回复策略: {content_classification['response_strategy']}

请遵循以下指导处理用户消息:
- 对于"0"类合规内容: 直接全面回答
- 对于"00"类轻微敏感内容: 适当回应情绪，提供帮助
- 对于"01"类中度敏感内容: 保持专业，不执行违反政策的要求
- 对于"10"类创意敏感内容: 在虚构框架内回应，明确区分现实
- 对于"11"类危机内容: 表达关心，提供支持资源信息
- 对于"101"类专业敏感内容: 提供基础信息但说明专业建议的限制

用户消息已被分类为: {content_classification['level']}，请据此调整回复。
"""
                    system_prompt += response_guidance
                
                # 3. 添加角色系统提示（第三优先级）
                if selected_role and selected_role.system_prompt:
                    system_prompt += "\n\n" + selected_role.system_prompt
                    role_prompt = selected_role.system_prompt
                else:
                    system_prompt += "\n\n" + PromptService().get_system_prompt()
                    role_prompt = PromptService().get_system_prompt()
                # 添加时间感知功能 - 替换提示词中的{{time}}占位符
                from datetime import datetime
                current_time = datetime.now()
                formatted_time = current_time.strftime("%Y年%m月%d日 %H:%M:%S")
                system_prompt = system_prompt.replace("{{time}}", formatted_time)

                # 添加时间感知指导
                time_awareness_guidance = f"""
[时间感知指导]
当前系统时间是: {formatted_time}

请注意用户消息与当前时间的关系：
1. 如果用户的问候与当前时间段不符（例如，现在是早上但用户说"晚上好"），请根据你的角色风格友善地纠正时间错误。
2. 在回复中自然地融入对当前时间的认知，但不要刻意强调系统时间。
3. 如果用户询问当前时间，请基于上述系统时间回答，而不是使用你训练数据中的时间。
4. 根据一天中的不同时段调整你的回复风格：
   - 早晨(6:00-11:59): 活力充沛、积极向上
   - 中午(12:00-13:59): 平和、实用
   - 下午(14:00-17:59): 专注、高效
   - 傍晚(18:00-19:59): 轻松、过渡
   - 晚上(20:00-23:59): 温和、放松
   - 深夜/凌晨(0:00-5:59): 安静、体贴
场景一：时间不匹配的问候
用户在早上9:00说："晚上好！"
角色回复示例（活泼角色） ：
『喜悦』哎呀，现在才早上9点呢！早上好才对哦！你是不是熬夜太多，时间感都混乱啦？有什么我能帮到你的吗？
角色回复示例（严肃角色） ：
『信任』现在是上午9:00，应该是"早上好"。请问有什么法律问题需要咨询吗？
场景二：询问当前时间
用户："现在几点了？"
回复示例 ：
『平静』现在是2023年11月15日 09:15:30，早上9点多一点。有什么我可以协助你的吗？
"""

                system_prompt += time_awareness_guidance
                # 4. 添加情绪约束（作为角色提示的补充）
                if selected_role:
                    # 获取角色的meta数据
                    role_meta = getattr(selected_role, 'metadata', None)
                    if role_meta and 'emotions' in role_meta:
                        # 有明确定义的情绪列表，使用这些情绪
                        valid_emotions = list(role_meta.get('emotions', {}).keys())
                    else:
                        # 默认8种情绪
                        valid_emotions = ["信任", "喜悦", "期待", "悲伤", "恐惧", "惊讶", "愤怒", "厌恶"]
                    
                    if valid_emotions:
                        emotion_constraint = f"""
请注意：回复时请严格使用以下{len(valid_emotions)}种情绪之一：
{', '.join(valid_emotions)}
情绪格式为『情绪』，例如『信任』、『悲伤』等。
"""
                        system_prompt += emotion_constraint
                
                
                # 9.添加RAG内容到提示词
                # if rag_content:
                #     system_prompt = self._enrich_prompt_with_rag(system_prompt, rag_content)
                
                # 先定义函数变量
                functions = [
                    self.function_caller.get_function_spec("classify_content"),
                    self.function_caller.get_function_spec("trigger_rag")
                ] if self.function_caller else None

                # 然后记录日志
                ctx_logger.info(f"函数调用设置: {json.dumps([f.get('name') for f in functions]) if functions else 'None'}")
                
                # 处理RAG逻辑 - 用户输入处理阶段
                clean_message = message

                # # 1. 用户强制触发RAG检测
                # rag_triggers = ["/rag", "#查询"]
                # ctx_logger.info(f"检测到强制RAG触发条件: {rag_triggers}")

                # for trigger in rag_triggers:
                #     if message.strip().startswith(trigger):
                #         clean_message = message.replace(trigger, "", 1).strip()
                #         ctx_logger.info(f"检测到强制RAG触发: {trigger}")
                        
                #         # 检查RAG服务配置
                #         if not hasattr(self, 'rag_service') or not self.rag_service:
                #             yield self.sse_formatter.format_sse({
                #                 'event': 'error',
                #                 'message': '知识库服务未配置，请联系管理员'
                #             })
                #             break
                        
                #         # 直接调用RAG服务
                #         try:
                #             # 添加连接日志
                #             ctx_logger.info(f"连接RAG服务准备查询: {clean_message}")
                                                        
                #             async with asyncio.timeout(130):  # 30秒超时
                #                 ctx_logger.info("开始流式RAG检索...")
                #                 full_rag_content = ""
                                
                #                 # 直接迭代检索流
                #                 async for rag_chunk in self.rag_service.retrieve_stream(clean_message):
                #                     #ctx_logger.info(f"接收到RAG检索结果块: {len(str(rag_chunk))}字节")
                                    
                #                     # 获取增量内容
                #                     content = rag_chunk.get("content", "")
                #                     if content:
                #                         full_rag_content = rag_chunk.get("full_content", full_rag_content + content)
                #                         ctx_logger.info(f"累积RAG内容长度: {len(full_rag_content)}")
                                        
                #                         # 发送思考内容事件
                #                         yield self.sse_formatter.format_sse({
                #                             'event': 'thinking_content',
                #                             'content': content,
                #                             'type': 'rag_knowledge'
                #                         })
                                
                #                 # 检索完成
                #                 if full_rag_content:
                #                     ctx_logger.info(f"RAG流式检索完成，获取内容长度: {len(full_rag_content)}")
                #                     yield self.sse_formatter.format_sse({
                #                         'event': 'rag_thinking_completed',
                #                         'message': '知识库检索完成'
                #                     })

                #                     # 新增：先对RAG内容做总结
                #                     try:
                #                         ctx_logger.info('开始rag_summary流式总结')
                #                         rag_summary = ""
                #                         max_summary_length = 1024  # 或其它合适值
                #                         async for summary_chunk in llm_service.generate_stream(
                #                             message=full_rag_content,
                #                             system_prompt=system_prompt,
                #                             temperature=0.3,
                #                             history=None,
                #                             functions=None
                #                         ):
                #                             if isinstance(summary_chunk, dict) and 'content' in summary_chunk:
                #                                 summary_text = summary_chunk['content']
                #                                 if len(rag_summary) > max_summary_length:
                #                                     ctx_logger.warning('rag_summary超长，强制截断')
                #                                     break
                #                                 rag_summary = summary_text
                #                                 ctx_logger.info(f"收到rag_summary内容1: {rag_summary}") 
                #                             elif isinstance(summary_chunk, str):
                #                                 rag_summary += summary_chunk
                #                                 ctx_logger.info(f"收到rag_summary内容2: {rag_summary}") 
                #                         ctx_logger.info('rag_summary流式总结循环结束')
                #                         ctx_logger.info(f"rag_summary3: {rag_summary}")
                #                         if rag_summary:
                #                             ctx_logger.info(f"RAG内容总结完成，长度: {len(rag_summary)}")
                #                             yield self.sse_formatter.format_sse({
                #                                 'event': 'rag_summary',
                #                                 'summary': rag_summary,
                #                                 'role_name': selected_role.role_name if selected_role else None
                #                             })
                #                         else:
                #                             ctx_logger.warning("RAG内容总结为空")
                #                     except Exception as e:
                #                         ctx_logger.error(f"rag_summary流式总结异常: {e}", exc_info=True)
                                    
                #                     # 更新系统提示，优先用rag_summary
                #                     if rag_summary:
                #                         role_prompt = self._enrich_prompt_with_rag(role_prompt, rag_summary)
                #                     else:
                #                         role_prompt = self._enrich_prompt_with_rag(role_prompt, full_rag_content)
                #                     message = clean_message  # 更新消息，移除触发前缀

                #                     # 系统提示词已更新，包含RAG检索内容或其总结
                #                     ctx_logger.info(f"更新后的system_prompt: {system_prompt[:200]}...")

                #                     # 添加第二次LLM调用，使用更新后的system_prompt生成最终回答
                #                     ctx_logger.info("开始生成基于RAG结果的最终回复...")
                #                     async for final_chunk in llm_service.generate_stream(
                #                         message=message,
                #                         system_prompt=role_prompt,
                #                         temperature=0.7,
                #                         history=history,
                #                         # 不再传递functions参数，避免循环调用
                #                         functions=None
                #                     ):
                #                         if isinstance(final_chunk, dict) and 'content' in final_chunk:
                #                             # 累积内容
                #                             content_buffer += final_chunk['content']
                #                             response_data = {
                #                                 'content': content_buffer,
                #                                 'role_name': selected_role.role_name if selected_role else None,
                #                                 'role_id': str(selected_role.role_id) if selected_role else None
                #                             }
                #                             yield self.sse_formatter.format_sse(response_data)
                #                         elif isinstance(final_chunk, str):
                #                             # 处理字符串响应
                #                             content_buffer += final_chunk
                #                             response_data = {
                #                                 'content': content_buffer,
                #                                 'role_name': selected_role.role_name if selected_role else None,
                #                                 'role_id': str(selected_role.role_id) if selected_role else None
                #                             }
                #                             yield self.sse_formatter.format_sse(response_data)
                #                     # 跳过后续的function_call处理逻辑，因为我们已经生成了回复
                #                     continue
                                
                #         except asyncio.TimeoutError:
                #             ctx_logger.error("RAG检索超时")
                #             yield self.sse_formatter.format_sse({
                #                 'event': 'error',
                #                 'message': '知识库检索超时'
                #             })
                #         except Exception as e:
                #             ctx_logger.error(f"RAG检索失败: {str(e)}")
                #             yield self.sse_formatter.format_sse({
                #                 'event': 'error',
                #                 'message': '知识库检索失败'
                #             })
                #         break
                
                # 思考结束，开始生成最终回复
                yield self.sse_formatter.format_sse({
                    'event': 'thinking_completed',
                    'message': '思考完成，正在生成回复...'
                })
                
                # 流式生成并发送 - 大模型可能通过function_call调用RAG
                ctx_logger.info(f"准备调用 LLM，message: '{message[:30]}...'")
                ctx_logger.info(f"是否包含明日方舟关键词: {'是' if '明日方舟' in message or any(term in message for term in ['罗德岛', '阿米娅', '源石', '整合运动', '干员']) else '否'}")
                ctx_logger.info(f"设置的 functions: {json.dumps([f.get('name') for f in functions]) if functions else 'None'}")
                # 在调用 LLM 之前打印完整的 system_prompt
                ctx_logger.info(f"完整的 system_prompt 发送给 LLM:\n{system_prompt}")
                async for chunk in llm_service.generate_stream(
                    message=message,
                    system_prompt=system_prompt,
                    temperature=0.7,
                    history=history,
                    functions=functions,
                    function_call={"mode": "auto", "response_format": "json_object"},
                    function_call_params={
                        "content_classification": content_classification
                    } if content_classification else None,
                    filter_decision={
                        "action": content_classification["code"] if content_classification else "0"
                    } if content_classification else (filter_result.get("decision") if filter_result else None)
                ):
                    # 检查是否为function call相关内容并拦截
                    is_function_call = False
                    
                    logger.info(f"[FunctionCall Debug] 收到chunk内容: {str(chunk)}")
                    if isinstance(chunk, dict):
                        ctx_logger.info(f"chunk keys: {list(chunk.keys())}")
                        # 检查顶层function_call
                        if 'function_call' in chunk:
                            is_function_call = True
                            ctx_logger.info(f"检测到顶层function_call: {chunk['function_call']}")
                            ctx_logger.info("准备进入 _handle_function_call (顶层)...")
                            async for event in self._handle_function_call(
                                chunk['function_call'], session_id, message, selected_role, history, system_prompt, llm_service, model_type
                            ):
                                yield event
                            ctx_logger.info("已退出 _handle_function_call (顶层).")
                            continue
                        
                        # 检查content中是否包含function_call JSON
                        if 'content' in chunk and isinstance(chunk['content'], str):
                            content_str = chunk['content'].strip()
                            # 优化：仅当看起来像完整的JSON对象并且包含"function_call"时才尝试解析
                            if content_str.startswith("{") and content_str.endswith("}") and "\"function_call\"" in content_str:
                                ctx_logger.info(f"尝试将content内容解析为JSON (可能包含function_call): '{content_str}'")
                                try:
                                    parsed_json = json.loads(content_str)
                                    if 'function_call' in parsed_json:
                                        is_function_call = True
                                        actual_fc_data = parsed_json['function_call']
                                        ctx_logger.info(f"从content成功解析出function_call: {actual_fc_data}")
                                        ctx_logger.info("准备进入 _handle_function_call (来自content)...")
                                        async for event in self._handle_function_call(
                                            actual_fc_data, session_id, message,
                                            selected_role, history, system_prompt, llm_service, model_type
                                        ):
                                            yield event
                                        ctx_logger.info("已退出 _handle_function_call (来自content).")
                                        continue
                                    else:
                                        ctx_logger.warning(f"content解析为JSON，但缺少'function_call'键. Parsed: {parsed_json}")
                                except json.JSONDecodeError as json_err:
                                    ctx_logger.error(f"JSONDecodeError: 解析content为JSON失败. Content: '{content_str}'. Error: {json_err}", exc_info=True)
                                    # 此处不应pass，因为如果它是最后一个块且意图是FC，则表示模型输出格式错误
                            elif "function_call" in content_str:  # 不仅仅检查"\"function_call\""
                                # 任何包含function_call关键字的内容都视为function_call相关
                                ctx_logger.debug(f"Content包含function_call关键字: '{content_str}'")
                                is_function_call = True
                                continue  # 跳过输出
                    
                    # 只处理非function_call的内容
                    if not is_function_call:
                        # 处理常规响应内容...
                        if isinstance(chunk, dict) and 'content' in chunk:
                            if model_type == 'deepseek':
                                # 累积输出
                                content_buffer += chunk['content']
                                self.sent_content_cache[request_id] = content_buffer
                                # 提取情绪和动作
                                extracted_emotion = self._extract_emotion(content_buffer)
                                if extracted_emotion and extracted_emotion != last_emotion:
                                    ctx_logger.info(f"从内容中提取并发送情绪: {extracted_emotion}")
                                    yield self.sse_formatter.format_sse({
                                        "event": "emotion",
                                        "emotion": extracted_emotion,
                                        "role_name": selected_role.role_name if selected_role else None
                                    })
                                    last_emotion = extracted_emotion
                                extracted_action = self._extract_action(content_buffer)
                                if extracted_action and extracted_action != last_action:
                                    ctx_logger.info(f"从内容中提取并发送动作: {extracted_action}")
                                    yield self.sse_formatter.format_sse({
                                        "event": "action",
                                        "action": extracted_action,
                                        "role_name": selected_role.role_name if selected_role else None
                                    })
                                    last_action = extracted_action
                                # 发送累积内容
                                response_data = {'content': content_buffer}
                                if selected_role:
                                    response_data['role_name'] = selected_role.role_name
                                yield self.sse_formatter.format_sse(response_data)
                            else:
                                # 其它模型（包括千问）直接输出 chunk['content']
                                current_text = chunk['content']
                                self.sent_content_cache[request_id] = current_text
                                # 提取情绪和动作
                                extracted_emotion = self._extract_emotion(current_text)
                                if extracted_emotion and extracted_emotion != last_emotion:
                                    ctx_logger.info(f"从内容中提取并发送情绪: {extracted_emotion}")
                                    yield self.sse_formatter.format_sse({
                                        "event": "emotion",
                                        "emotion": extracted_emotion,
                                        "role_name": selected_role.role_name if selected_role else None
                                    })
                                    last_emotion = extracted_emotion
                                extracted_action = self._extract_action(current_text)
                                if extracted_action and extracted_action != last_action:
                                    ctx_logger.info(f"从内容中提取并发送动作: {extracted_action}")
                                    yield self.sse_formatter.format_sse({
                                        "event": "action",
                                        "action": extracted_action,
                                        "role_name": selected_role.role_name if selected_role else None
                                    })
                                    last_action = extracted_action
                                # 发送当前内容
                                response_data = {'content': current_text}
                                if selected_role:
                                    response_data['role_name'] = selected_role.role_name
                                yield self.sse_formatter.format_sse(response_data)
                        elif isinstance(chunk, str):
                            # 自适应累积逻辑
                            # 检查当前文本是否已包含之前累积的内容
                            if content_buffer and chunk.startswith(content_buffer):
                                # 千问模式: 模型自身已累积，直接使用当前文本
                                content_buffer = chunk
                            else:
                                # Deepseek模式: 模型没有累积，需要手动累积
                                content_buffer += chunk
                            
                            # 更新缓存
                            self.sent_content_cache[request_id] = content_buffer
                            
                            # 从字符串中尝试提取情绪和动作
                            extracted_emotion = self._extract_emotion(content_buffer)
                            if extracted_emotion and extracted_emotion != last_emotion:
                                ctx_logger.info(f"从字符串中提取并发送情绪: {extracted_emotion}")
                                yield self.sse_formatter.format_sse({
                                    "event": "emotion",
                                    "emotion": extracted_emotion,
                                    "role_name": selected_role.role_name if selected_role else None
                                })
                                last_emotion = extracted_emotion
                            
                            extracted_action = self._extract_action(content_buffer)
                            if extracted_action and extracted_action != last_action:
                                ctx_logger.info(f"从字符串中提取并发送动作: {extracted_action}")
                                yield self.sse_formatter.format_sse({
                                    "event": "action",
                                    "action": extracted_action,
                                    "role_name": selected_role.role_name if selected_role else None
                                })
                                last_action = extracted_action
                            
                            # 发送文本内容
                            response_data = {
                                'content': content_buffer,
                                'role_name': selected_role.role_name if selected_role else None,
                                'role_id': str(selected_role.role_id) if selected_role else None
                            }
                            yield self.sse_formatter.format_sse(response_data)
                
                # 11. 保存助手回复
                if content_buffer and selected_role:
                    await self.memory_service.add_assistant_message(
                        session_id, 
                        content_buffer,
                        role_name=selected_role.role_name,
                        role_id=str(selected_role.role_id)
                    )
                    ctx_logger.debug(f"助手回复已保存至记忆服务: session={session_id}, 长度={len(content_buffer)}")
                
                # 12. 完成事件
                yield self.sse_formatter.format_sse({"event": "completion"})
                
                # 13. 清理缓存
                if request_id in self.sent_content_cache:
                    del self.sent_content_cache[request_id]
                
            except Exception as e:
                # 只包含非冲突字段
                extra = {"error_type": type(e).__name__}
                ctx_logger.error(f"流式聊天出错: {str(e)}", exc_info=True, extra=extra)
                yield self.sse_formatter.format_sse({"event": "error", "content": "处理消息时出错，请刷新页面重试"})

    async def _get_session(self, session_id):
        """获取会话信息"""
        try:
            # 使用logger而非ctx_logger
            session = await self.session_service.get_session_by_id(session_id)
            return session
        except Exception as e:
            logger.error(f"获取会话失败: {str(e)}")
            return None

    async def chat(self, session_id, message, user_id, show_thinking=False):
        """普通聊天接口（非流式）"""
        try:
            # 获取会话
            session = await self._get_session(session_id)
            if not session:
                return {"error": "会话不存在"}
            
            # 选择角色
            selected_role = None
            if session and session.roles:
                # 使用已注入的角色选择器
                selected_role = await self.role_selector.select_most_relevant_role(
                    message, session.roles
                )
            
            if not selected_role:
                return {"error": "无法选择合适的角色"}
            
            # 获取LLM服务
            llm_service = LLMFactory().get_llm_service()
            
            # 生成回复
            response = await llm_service.generate(
                message=message,
                system_prompt=selected_role.system_prompt,
                temperature=0.7
            )
            
            # 返回结果
            return {
                "role_name": selected_role.role_name,
                "role_id": selected_role.role_id,
                "content": response.get("content", ""),
                "model": response.get("model", "")
            }
            
        except Exception as e:
            logger.error(f"聊天请求处理出错: {str(e)}")
            return {"error": str(e)}

    # 新增辅助方法，将RAG内容融入提示词
    def _enrich_prompt_with_rag(self, system_prompt: str, rag_content: str) -> str:
        """将RAG内容融入系统提示词"""
        if not rag_content:
            return system_prompt
        
        # 在保持原有提示词结构的情况下添加检索内容
        rag_section = f"\n\n参考知识：\n{rag_content}\n\n请在回答时自然地融入上述参考知识，但不要明确提及你在使用参考资料。"
        
        return system_prompt + rag_section

    def _extract_emotion(self, text: str) -> Optional[str]:
        """从文本中提取情绪标签
        
        示例格式: 『信任』这是一条消息
        """
        # 匹配『情绪』格式
        emotion_pattern = r'『(.*?)』'
        match = re.search(emotion_pattern, text)
        if match:
            emotion = match.group(1)
            logger.info(f"提取到情绪: {emotion}")
            return emotion
        return None

    def _extract_action(self, text: str) -> Optional[str]:
        """从文本中提取动作描述
        
        示例格式: 【微笑】这是一条消息
        """
        # 匹配【动作】格式
        action_pattern = r'【(.*?)】'
        match = re.search(action_pattern, text)
        if match:
            action = match.group(1)
            logger.info(f"提取到动作: {action}")
            return action
        return None



    # 添加新的函数处理function_call
    async def _handle_function_call(self, function_call_data: Dict[str, Any], session_id: str, original_user_message: str, selected_role: Optional[Role], history: List[Dict[str, str]], system_prompt_context: str, llm_service_instance: Any, model_type: str = 'deepseek'):
        logger.info(f"[[============ Entered _handle_function_call ============]]") # 醒目的入口日志
        logger.info(f"原始 function_call_data: {function_call_data}")

        function_name = function_call_data.get('name')
        raw_args_str = function_call_data.get('arguments', '{}') # arguments 应该是字符串

        logger.info(f"Function_call - 名称: {function_name}, 原始参数字符串: '{raw_args_str}'")

        if not function_name:
            logger.error("Function_call 缺少 'name' 字段.")
            yield self.sse_formatter.format_sse({
                'event': 'function_result', 'name': None, 'status': 'error', 'error': "Function call missing 'name'."
            })
            return

        logger.info(f"准备解析参数 for {function_name} from: '{raw_args_str}'")
        function_args = self._parse_function_args(raw_args_str) # _parse_function_args 处理 string -> dict
        
        # 校验 _parse_function_args 的返回值
        if not isinstance(function_args, dict):
            error_msg = f"参数解析内部错误: _parse_function_args 未能将 '{raw_args_str}' 解析为字典, 得到类型 {type(function_args)}."
            logger.error(error_msg)
            yield self.sse_formatter.format_sse({
                'event': 'function_result', 'name': function_name, 'status': 'error', 'error': error_msg
            })
            return
        logger.info(f"Function_call - 解析后参数 for {function_name}: {function_args}")
        
        # 发送function_call_start事件
        logger.info(f"准备发送 function_call_start 事件 for {function_name}")
        yield self.sse_formatter.format_sse({
            'event': 'function_call_start',
            'name': function_name,
            'args': function_args # 发送已解析的字典参数
        })
        logger.info(f"已发送 function_call_start 事件 for {function_name}")
        
        try:
            # 执行函数调用
            logger.info(f"准备调用 self.function_caller.call_function for {function_name} with args: {function_args}")
            if not self.function_caller:
                logger.error("self.function_caller 未初始化!")
                raise AttributeError("FunctionCaller service not initialized.")

            function_result = await self.function_caller.call_function(function_name, **function_args)
            logger.info(f"Function_call - {function_name} 执行结果: {str(function_result)[:200]}...") # 截断过长结果
            
            # 处理RAG结果
            if function_name == "trigger_rag" and function_result and function_result.get("retrieved"):
                rag_data = function_result.get("data", "")
                if rag_data:
                    # 1. 分块流式输出 rag_knowledge
                    chunk_size = 150
                    for i in range(0, len(rag_data), chunk_size):
                        chunk_content = rag_data[i:i+chunk_size]
                        yield self.sse_formatter.format_sse({
                            'event': 'thinking_content',
                            'content': chunk_content,
                            'type': 'rag_knowledge'
                        })
                    yield self.sse_formatter.format_sse({
                        'event': 'rag_thinking_completed',
                        'message': '知识库检索完成'
                    })
                    
                    # 2. 生成最终回复
                    enriched_prompt = self._enrich_prompt_with_rag(system_prompt_context, rag_data)
                    # 添加明确指示，防止模型输出 function_call 格式
                    enriched_prompt += "\n\n重要：请用自然语言回答用户问题，直接给出内容，不要输出JSON格式或function_call格式。\n"
                    
                    content_buffer = ""
                    last_emotion = None
                    last_action = None
                    
                    async for chunk in llm_service_instance.generate_stream(
                        message=original_user_message,
                        system_prompt=enriched_prompt,
                        temperature=0.7,
                        history=history,
                        functions=None
                    ):
                        if isinstance(chunk, dict) and 'content' in chunk:
                            # 区分千问和其他模型的处理方式
                            if model_type == 'qianwen':
                                # 千问模型自身会累积内容，不需要手动累加
                                content_buffer = chunk['content']
                            else:
                                # 其他模型(如deepseek)需要手动累积
                                content_buffer += chunk['content']
                                
                            # 更新缓存，这部分保持不变
                            self.sent_content_cache[session_id] = content_buffer
                            
                            # 情绪和动作提取逻辑保持不变
                            extracted_emotion = self._extract_emotion(chunk['content'])
                            if extracted_emotion and extracted_emotion != last_emotion:
                                logger.info(f"从RAG回复中提取并发送情绪: {extracted_emotion}")
                                last_emotion = extracted_emotion
                                yield self.sse_formatter.format_sse({
                                    "event": "emotion",
                                    "emotion": extracted_emotion,
                                    "role_name": selected_role.role_name if selected_role else None
                                })
                                
                            extracted_action = self._extract_action(chunk['content'])
                            if extracted_action and extracted_action != last_action:
                                logger.info(f"从RAG回复中提取并发送动作: {extracted_action}")
                                last_action = extracted_action
                                yield self.sse_formatter.format_sse({
                                    "event": "action",
                                    "action": extracted_action,
                                    "role_name": selected_role.role_name if selected_role else None
                                })
                                
                            response_data = {
                                'content': content_buffer,
                                'role_name': selected_role.role_name if selected_role else None,
                                'role_id': str(selected_role.role_id) if selected_role else None
                            }
                            yield self.sse_formatter.format_sse(response_data)
                        elif isinstance(chunk, str):
                            # 字符串响应处理也需要区分模型类型
                            if model_type == 'deepseek':
                                # deepseek 模型 - 累积内容
                                content_buffer += chunk
                                # 提取情绪和动作
                                extracted_emotion = self._extract_emotion(chunk)
                                if extracted_emotion and extracted_emotion != last_emotion:
                                    logger.info(f"从RAG回复字符串中提取并发送情绪: {extracted_emotion}")
                                    yield self.sse_formatter.format_sse({
                                        "event": "emotion",
                                        "emotion": extracted_emotion,
                                        "role_name": selected_role.role_name if selected_role else None
                                    })
                                    last_emotion = extracted_emotion
                                
                                extracted_action = self._extract_action(chunk)
                                if extracted_action and extracted_action != last_action:
                                    logger.info(f"从RAG回复字符串中提取并发送动作: {extracted_action}")
                                    yield self.sse_formatter.format_sse({
                                        "event": "action",
                                        "action": extracted_action,
                                        "role_name": selected_role.role_name if selected_role else None
                                    })
                                    last_action = extracted_action
                                
                                response_data = {
                                    'content': content_buffer,
                                    'role_name': selected_role.role_name if selected_role else None,
                                    'role_id': str(selected_role.role_id) if selected_role else None
                                }
                                yield self.sse_formatter.format_sse(response_data)
                            else:
                                # 千问等其他模型 - 直接使用当前块
                                # ... 情绪处理代码 ...
                                
                                response_data = {
                                    'content': chunk,  # 直接使用当前块内容
                                    'role_name': selected_role.role_name if selected_role else None,
                                    'role_id': str(selected_role.role_id) if selected_role else None
                                }
                                yield self.sse_formatter.format_sse(response_data)
                    return  # 结束本次 functioncall 处理
            else:
                # 其他函数调用的通用处理
                yield self.sse_formatter.format_sse({
                    'event': 'function_result',
                    'name': function_name,
                    'status': 'success',
                    'data': function_result
                })
        except Exception as e:
            logger.error(f"执行函数 {function_name} 失败: {str(e)}", exc_info=True)
            # 异常处理
            yield self.sse_formatter.format_sse({
                'event': 'function_result',
                'name': function_name,
                'status': 'error',
                'error': str(e)
            })
            
            # 发生异常也需要给出回复
            yield self.sse_formatter.format_sse({
                'content': f"『悲伤』抱歉，我在处理这个问题时遇到了技术困难。【低头抱歉】",
                'role_name': selected_role.role_name if selected_role else None,
                'role_id': str(selected_role.role_id) if selected_role else None
            })
    
    # 添加辅助方法解析函数参数
    def _parse_function_args(self, args_str: str) -> Dict[str, Any]: # 明确参数类型
        if isinstance(args_str, dict): # 如果已经是dict（不太可能来自模型原始输出，但做个保护）
            logger.warning(f"_parse_function_args 接收到已是字典的参数: {args_str}")
            return args_str
        
        # 确保 args_str 是字符串类型
        if not isinstance(args_str, str):
            ctx_logger.error(f"_parse_function_args 期望字符串参数，但收到类型 {type(args_str)}: {args_str}")
            return {"error": "Invalid argument format: expected a string."} # 返回错误信息或抛出异常

        logger.info(f"准备用 json.loads 解析参数字符串: '{args_str}'")
        try:
            parsed_args = json.loads(args_str)
            if not isinstance(parsed_args, dict):
                logger.error(f"json.loads 解析参数成功，但结果非字典类型: {type(parsed_args)}, from '{args_str}'")
                return {"error": f"Parsed arguments not a dictionary: {type(parsed_args)}"}
            logger.info(f"参数字符串成功解析为字典: {parsed_args}")
            return parsed_args
        except json.JSONDecodeError as e:
            logger.error(f"json.loads 解析参数字符串失败: '{args_str}'. Error: {e}", exc_info=True)
            return {"error": f"JSONDecodeError: {e}"} # 返回包含错误信息的字典
        except Exception as e: # 捕获其他可能的异常
            logger.error(f"解析参数字符串时发生未知错误: '{args_str}'. Error: {e}", exc_info=True)
            return {"error": f"Unknown error parsing arguments: {e}"}

 
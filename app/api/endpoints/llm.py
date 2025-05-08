from fastapi import APIRouter, Depends, Query, WebSocket, Request
from typing import Optional
from app.utils.exceptions import handle_exceptions
from app.utils.logging import logger
from app.services.chat_service import ChatService
from app.api.deps import get_chat_service, get_session_service
from fastapi.responses import StreamingResponse
import asyncio

router = APIRouter(prefix="/llm", tags=["LLM服务"])

@router.get("/chatstream")
@handle_exceptions(logger)
async def chat_stream_endpoint(
    session_id: str = Query(..., description="会话ID"),
    message: str = Query(..., description="用户消息"),
    user_id: Optional[str] = Query(None, description="用户ID"),
    show_thinking: bool = Query(False, description="是否显示思考过程"),
    chat_service: ChatService = Depends(get_chat_service)
):
    """流式聊天API接口，返回SSE格式的流式响应"""
    
    async def event_generator():
        async for chunk in chat_service.chat_stream(
            session_id=session_id,
            message=message,
            user_id=user_id or "anonymous",
            show_thinking=show_thinking
        ):
            yield chunk
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
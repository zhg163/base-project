from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional

from app.api.deps import get_chat_service, get_memory_service
from app.services.chat_service import ChatService
from app.services.ai.memory.memory_service import MemoryService
from app.utils.exceptions import handle_exceptions
from app.utils.logging import logger

router = APIRouter()

@router.get("/chat")
@handle_exceptions(logger)
async def chat(
    message: str,
    session_id: str,
    user_id: Optional[str] = "anonymous",
    show_thinking: Optional[bool] = False,
    chat_service: ChatService = Depends(get_chat_service)
):
    """普通聊天API端点"""
    response = await chat_service.chat(
        session_id=session_id,
        message=message, 
        user_id=user_id,
        show_thinking=show_thinking
    )
    return response

@router.get("/chatstream")
@handle_exceptions(logger)
async def chat_stream(
    message: str,
    session_id: str,
    user_id: Optional[str] = "anonymous",
    show_thinking: Optional[bool] = Query(False),
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    流式聊天API端点，使用SSE传输
    """
    async def event_generator():
        async for chunk in chat_service.chat_stream(
            session_id=session_id,
            message=message,
            user_id=user_id,
            show_thinking=show_thinking,
            format="sse"
        ):
            yield chunk
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 针对Nginx的缓冲设置
        }
    )

@router.get("/chatstreamrag")
@handle_exceptions(logger)
async def chat_stream_rag(
    message: str,
    session_id: str,
    user_id: Optional[str] = "anonymous",
    show_thinking: Optional[bool] = Query(True),
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    带知识库检索的流式聊天API端点，使用SSE传输
    """
    async def event_generator():
        try:
            async for chunk in chat_service.chat_stream_rag(
                session_id=session_id,
                message=message,
                user_id=user_id,
                show_thinking=show_thinking,
                format="sse"
            ):
                yield chunk
        except Exception as e:
            logger.error(f"生成RAG流式响应出错: {str(e)}", exc_info=True)
            yield f"data: {{'error': '{str(e)}'}}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/chat")
@handle_exceptions(logger)
async def chat_endpoint(request: Request, chat_service: ChatService = Depends(get_chat_service)):
    """处理POST请求的聊天API端点"""
    try:
        data = await request.json()
        message = data.get("message")
        session_id = data.get("session_id")
        user_id = data.get("user_id", "anonymous")
        show_thinking = data.get("show_thinking", False)
        
        if not message or not session_id:
            return JSONResponse(
                status_code=400,
                content={"error": "缺少必要参数: message或session_id"}
            )
        
        response = await chat_service.chat(
            session_id=session_id,
            message=message,
            user_id=user_id,
            show_thinking=show_thinking
        )
        return response
    except Exception as e:
        logger.error(f"请求JSON解析失败: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"处理请求时出错: {str(e)}"}
        )

@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    memory_service: MemoryService = Depends(get_memory_service)
):
    """获取会话的完整历史记录"""
    try:
        history = await memory_service.get_full_history(session_id, limit)
        return {"history": history}
    except Exception as e:
        logger.error(f"获取会话历史失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取会话历史失败: {str(e)}"
        )
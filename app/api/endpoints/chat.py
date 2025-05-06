from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional
import logging

from app.api.deps import get_chat_service
from app.services.chat_service import ChatService

router = APIRouter()

@router.get("/chat")
async def chat(
    message: str,
    session_id: str,
    user_id: Optional[str] = "anonymous",
    show_thinking: Optional[bool] = False,
    chat_service: ChatService = Depends(get_chat_service)
):
    """普通聊天API端点"""
    try:
        response = await chat_service.chat(
            session_id=session_id,
            message=message, 
            user_id=user_id,
            show_thinking=show_thinking
        )
        return response
    except Exception as e:
        logging.error(f"聊天请求处理出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")

@router.get("/chatstream")
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
        try:
            async for chunk in chat_service.chat_stream(
                session_id=session_id,
                message=message,
                user_id=user_id,
                show_thinking=show_thinking,
                format="sse"
            ):
                yield chunk
        except Exception as e:
            logging.error(f"生成流式响应出错: {str(e)}")
            yield f"data: {{'error': '{str(e)}'}}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 针对Nginx的缓冲设置
        }
    )

@router.get("/chatstreamrag")
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
            logging.error(f"生成RAG流式响应出错: {str(e)}")
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
        logging.error(f"处理POST聊天请求出错: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"处理请求时出错: {str(e)}"}
        )
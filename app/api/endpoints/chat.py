from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from fastapi.responses import StreamingResponse

from app.services.chat_service import ChatService

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    model_type: str = "deepseek"
    system_prompt: Optional[str] = None
    temperature: float = 0.7

class ChatResponse(BaseModel):
    content: str
    model: str
    session_id: str
    request_id: str
    timestamp: str
    finish_reason: str

@router.post("/chat")
async def chat_post(
    request: ChatRequest,
    chat_service: ChatService = Depends()
):
    """聊天接口 - POST方法"""
    # 获取生成器而不是尝试await它
    generator = chat_service.process_message_stream(
        message=request.message,
        session_id=request.session_id,
        model_type=request.model_type,
        system_prompt=request.system_prompt,
        temperature=request.temperature
    )
    
    # 返回流式响应
    return StreamingResponse(
        content=generator,
        media_type="text/event-stream"
    )

@router.get("/chat", response_model=ChatResponse)
async def chat_get(
    message: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    show_thinking: Optional[bool] = False,
    model_type: str = "deepseek",
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    chat_service: ChatService = Depends()
):
    """聊天接口 - GET方法"""
    response = await chat_service.process_message(
        message=message,
        session_id=session_id,
        model_type=model_type,
        system_prompt=system_prompt,
        temperature=temperature
    )
    
    # 检查是否有错误
    if "error" in response:
        raise HTTPException(
            status_code=response["error"]["code"],
            detail=response["error"]["message"]
        )
    
    return response

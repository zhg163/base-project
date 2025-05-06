from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
from fastapi.responses import StreamingResponse

from app.services.chat_service import ChatService
from app.api.deps import get_chat_service  # 导入依赖函数

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
async def chat(
    request: Request,
    chat_service: ChatService = Depends(get_chat_service)
):
    """处理聊天请求"""
    # 使用JSON而不是表单
    body = await request.json()
    
    # 从JSON中提取参数(注意这里使用body而不是form_data)
    message = body.get("message")
    session_id = body.get("session_id")
    
    # 添加其他有效参数
    model_type = body.get("model_type")
    system_prompt = body.get("system_prompt")
    temperature = body.get("temperature", 0.7)
    
    if not message:
        raise HTTPException(status_code=422, detail="消息内容不能为空")
    
    # 调用服务，只传递方法支持的参数
    return StreamingResponse(
        chat_service.process_message_stream(
            message=message,
            session_id=session_id,
            model_type=model_type,
            system_prompt=system_prompt,
            temperature=temperature
        ),
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

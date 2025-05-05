from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Body, Query, status
from app.models.entities.mongo_models import Session, RoleReference
from app.services.storage.session_repository import SessionRepository
from app.api.deps import get_session_repository, get_session_service
from app.models.schemas.session import SessionCreate, SessionResponse, SessionUpdate
from app.utils.logging import logger
from datetime import datetime
from app.services.session_service import SessionService

router = APIRouter()

class SessionController:
    """会话控制器，处理会话相关的HTTP请求"""
    
    @router.get("", response_model=List[SessionResponse])
    async def get_all_sessions(
        user_id: Optional[str] = Query(None),
        page: int = Query(1, ge=1, description="页码"),
        limit: int = Query(10, ge=1, le=100, description="每页数量"),
        session_repository: SessionRepository = Depends(get_session_repository)
    ):
        """获取所有会话，支持分页"""
        filter_dict = {}
        if user_id:
            filter_dict["user_id"] = user_id
        
        # 计算跳过的记录数
        skip = (page - 1) * limit
        
        # 使用分页参数查询
        sessions = await session_repository.find_many(
            filter_dict=filter_dict,
            skip=skip,
            limit=limit
        )
        return sessions

    @router.get("/{session_id}", response_model=SessionResponse)
    async def get_session(
        session_id: str,
        session_repository: SessionRepository = Depends(get_session_repository)
    ):
        """获取特定会话"""
        # 使用session_id字段查询
        session = await session_repository.find_by_session_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        return session

    @router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
    async def create_session(
        session_data: SessionCreate,
        session_service: SessionService = Depends(get_session_service)
    ):
        """创建新会话"""
        created_session = await session_service.create_session(
            class_name=session_data.class_name,
            user_id=session_data.user_id,
            user_name=session_data.user_name,
            roles=[role.model_dump() for role in session_data.roles],
            class_id=session_data.class_id
        )
        return created_session

    @router.put("/{session_id}", response_model=SessionResponse)
    async def update_session(
        session_id: str,
        session_data: SessionUpdate,
        session_service: SessionService = Depends(get_session_service)
    ):
        """更新会话信息"""
        # 获取会话
        session = await session_service.get_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 更新字段
        update_data = session_data.model_dump(exclude_unset=True)
        
        # 特殊处理角色列表
        if "roles" in update_data:
            roles_data = [
                RoleReference(
                    role_id=role.role_id, 
                    role_name=role.role_name,
                    system_prompt=role.system_prompt
                )
                for role in session_data.roles
            ]
            session.roles = roles_data
            del update_data["roles"]
        
        # 更新其他字段
        for key, value in update_data.items():
            setattr(session, key, value)
        
        # 添加更新时间
        session.updated_at = datetime.utcnow()
        
        updated_session = await session_service.session_repository.update(session)
        return updated_session

    @router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_session(
        session_id: str,
        session_service: SessionService = Depends(get_session_service)
    ):
        """删除会话"""
        # 使用session_id查询
        session = await session_service.get_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 使用服务方法删除
        result = await session_service.delete_session(session_id)
        if not result:
            raise HTTPException(status_code=500, detail="删除会话失败")
        return None 
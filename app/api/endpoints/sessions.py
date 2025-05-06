from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Body, Query, status
from app.models.entities.mongo_models import Session, RoleReference
from app.services.storage.session_repository import SessionRepository
from app.api.deps import get_session_repository, get_session_service, get_role_repository
from app.models.schemas.session import SessionCreate, SessionResponse, SessionUpdate
from app.utils.logging import logger
from datetime import datetime
from app.services.session_service import SessionService
from bson.objectid import ObjectId

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
        session_service: SessionService = Depends(get_session_service)
    ):
        """获取会话详情"""
        session = await session_service.get_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 添加日志 - 检查API响应前的数据
        logger.info(f"Session to be returned in API: {session_id}")
        for i, role in enumerate(session.roles):
            logger.info(f"API response role {i}: id={role.role_id}, name={role.role_name}")
            if hasattr(role, 'system_prompt'):
                logger.info(f"API role {i} system_prompt: {role.system_prompt or 'None'}")
            else:
                logger.warning(f"API role {i} has no system_prompt attribute")
        
        # 检查model_dump后的数据
        session_dict = session.model_dump()
        logger.info(f"Session after model_dump - keys: {session_dict.keys()}")
        if 'roles' in session_dict:
            for i, role in enumerate(session_dict['roles']):
                logger.info(f"Dumped role {i} keys: {role.keys()}")
                if 'system_prompt' in role:
                    logger.info(f"Dumped role {i} system_prompt: {role.get('system_prompt')}")
                else:
                    logger.warning(f"Dumped role {i} missing system_prompt key")
        
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
        
        # 更新MongoDB
        updated_session = await session_service.session_repository.update(session)
        
        # 同步更新到Redis
        if session_service.redis_service:
            # 转换为字典
            session_dict = updated_session.model_dump()
            # 保存到Redis
            await session_service.redis_service.set_session(
                session_id=session_id,
                session_data=session_dict
            )
        
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
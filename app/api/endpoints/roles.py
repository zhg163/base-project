from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Body, status
from app.models.entities.mongo_models import Role
from app.services.storage.mongo_repository import MongoRepository
from app.api.deps import get_role_repository
from app.models.schemas.role import RoleCreate, RoleResponse, RoleUpdate
from app.utils.logging import logger
from pydantic import BaseModel

router = APIRouter()

@router.get("", response_model=List[RoleResponse])
async def get_all_roles(
    role_repo: MongoRepository = Depends(get_role_repository),
    game_name: Optional[str] = None
):
    """获取所有角色"""
    if game_name:
        roles = await role_repo.find_many({"game_name": game_name})
    else:
        roles = await role_repo.find_many({})
    return roles

@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: str,
    role_repo: MongoRepository = Depends(get_role_repository)
):
    """获取特定角色"""
    role = await role_repo.get(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    return role

@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    role_repo: MongoRepository = Depends(get_role_repository)
):
    """创建新角色"""
    # 检查角色名是否已存在
    if await role_repo.find_one({"name": role_data.name}):
        raise HTTPException(status_code=400, detail="角色名已存在")
    
    role = Role(**role_data.model_dump())
    created_role = await role_repo.create(role)
    return created_role

@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    role_data: RoleUpdate,
    role_repo: MongoRepository = Depends(get_role_repository)
):
    """更新角色信息"""
    role = await role_repo.get(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    # 更新角色字段
    update_data = role_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(role, key, value)
    
    updated_role = await role_repo.update(role)
    return updated_role

@router.delete("/delete-all", response_model=Dict[str, int])
async def delete_all_roles(
    role_repo: MongoRepository = Depends(get_role_repository)
):
    """删除所有角色数据"""
    deleted_count = await role_repo.delete_all()
    return {"deleted_count": deleted_count}

@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: str,
    role_repo: MongoRepository = Depends(get_role_repository)
):
    """删除角色"""
    role = await role_repo.get(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    await role_repo.delete(role_id)
    return None

@router.post("/check-existing", response_model=Dict[str, Any])
async def check_existing_roles(
    roles: List[Dict[str, Any]] = Body(...),
    role_repo: MongoRepository = Depends(get_role_repository)
):
    """检查角色是否已存在"""
    existing_roles = []
    new_roles = []
    
    for role_data in roles:
        role_name = role_data.get("name")
        if await role_repo.find_one({"name": role_name}):
            existing_roles.append(role_name)
        else:
            new_roles.append(role_data)
    
    return {
        "existingRoles": existing_roles,
        "newRoles": new_roles
    }

@router.post("/add-new", response_model=Dict[str, Any])
async def add_new_roles(
    roles: List[Dict[str, Any]] = Body(...),
    role_repo: MongoRepository = Depends(get_role_repository)
):
    """添加多个新角色"""
    inserted_count = 0
    
    for role_data in roles:
        role = Role(**role_data)
        await role_repo.create(role)
        inserted_count += 1
    
    return {"insertedCount": inserted_count} 
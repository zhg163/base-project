from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Body, status
from app.models.entities.mongo_models import User
from app.services.storage.mongo_repository import MongoRepository
from app.api.deps import get_user_repository
from app.models.schemas.user import UserCreate, UserResponse, UserUpdate
from app.core.security import get_password_hash

router = APIRouter()

@router.get("", response_model=List[UserResponse])
async def get_all_users(
    user_repo: MongoRepository = Depends(get_user_repository)
):
    """获取所有用户"""
    users = await user_repo.find_many({})
    return users

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    user_repo: MongoRepository = Depends(get_user_repository)
):
    """获取特定用户"""
    user = await user_repo.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    user_repo: MongoRepository = Depends(get_user_repository)
):
    """创建新用户"""
    # 检查用户名是否已存在
    if await user_repo.find_one({"username": user_data.username}):
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 如果提供了邮箱，检查邮箱是否已存在
    if user_data.email and await user_repo.find_one({"email": user_data.email}):
        raise HTTPException(status_code=400, detail="邮箱已存在")
    
    user = User(**user_data.model_dump())
    created_user = await user_repo.create(user)
    return created_user

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    user_repo: MongoRepository = Depends(get_user_repository)
):
    """更新用户信息"""
    user = await user_repo.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 更新用户字段
    update_data = user_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    
    updated_user = await user_repo.update(user)
    return updated_user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    user_repo: MongoRepository = Depends(get_user_repository)
):
    """删除用户"""
    user = await user_repo.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    await user_repo.delete(user_id)
    return None

@router.post("/check-existing", response_model=Dict[str, Any])
async def check_existing_users(
    users: List[Dict[str, Any]] = Body(...),
    user_repo: MongoRepository = Depends(get_user_repository)
):
    """检查用户是否已存在"""
    existing_users = []
    new_users = []
    
    for user_data in users:
        username = user_data.get("username")
        if await user_repo.find_one({"username": username}):
            existing_users.append(username)
        else:
            new_users.append(user_data)
    
    return {
        "existingUsers": existing_users,
        "newUsers": new_users
    }

@router.post("/add-new", response_model=Dict[str, Any])
async def add_new_users(
    users: List[Dict[str, Any]] = Body(...),
    user_repo: MongoRepository = Depends(get_user_repository)
):
    """添加多个新用户"""
    inserted_count = 0
    
    for user_data in users:
        # 不再需要添加默认密码
        user = User(**user_data)
        await user_repo.create(user)
        inserted_count += 1
    
    return {"insertedCount": inserted_count}

@router.get("/name/{name}", response_model=UserResponse)
async def get_user_by_username(
    name: str,
    user_repo: MongoRepository = Depends(get_user_repository)
):
    """
    根据用户名查询用户信息
    """
    user = await user_repo.find_one({"name": name})
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user 
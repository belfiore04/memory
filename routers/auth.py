from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional
from jose import JWTError, jwt
from services.auth_service import AuthService, ALGORITHM, SECRET_KEY
import uuid

router = APIRouter(prefix="/auth", tags=["Auth"])
auth_service = AuthService()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

class UserRegister(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = auth_service.get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    return user

@router.post("/register")
async def register(user_in: UserRegister):
    if auth_service.get_user(user_in.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    
    user_id = str(uuid.uuid4())
    success = auth_service.create_user(user_id, user_in.username, user_in.password)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create user")
    
    return {"message": "User registered successfully", "user_id": user_id}

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = auth_service.get_user(form_data.username)
    if not user or not auth_service.verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 检查用户状态
    if not user.get("is_active", 1):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is banned",
        )
    
    access_token = auth_service.create_access_token(data={"sub": user["id"]})
    return {"access_token": access_token, "token_type": "bearer", "user_id": user["id"]}

@router.get("/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"], 
        "username": current_user["username"],
        "role": current_user.get("role", "user"),
        "is_active": current_user.get("is_active", 1),
        "ai_name": current_user.get("ai_name"),
        "persona": current_user.get("persona")
    }

class AISettings(BaseModel):
    ai_name: Optional[str] = None
    persona: Optional[str] = None

@router.get("/persona")
async def get_persona(current_user: dict = Depends(get_current_user)):
    """获取用户 AI 设定 (Persona)"""
    return {
        "ai_name": current_user.get("ai_name"),
        "persona": current_user.get("persona")
    }

@router.put("/persona")
async def update_persona(settings: AISettings, current_user: dict = Depends(get_current_user)):
    """更新用户 AI 设定 (Persona)"""
    success = auth_service.update_user_settings(current_user["id"], settings.ai_name, settings.persona)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update settings")
    return {"message": "Persona updated successfully"}

async def get_current_admin(current_user: dict = Depends(get_current_user)):
    """依赖注入：验证当前用户是否为管理员"""
    role = current_user.get("role", "user")
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

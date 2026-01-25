from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.dependencies.clients import get_db
from src.api.dependencies.auth import get_auth_service, oauth2_scheme, get_current_user_required
from src.api.dependencies.clients import get_redis
from src.api.services.auth_service import AuthService
from src.api.selectors.user.get_user import get_user_by_email
from src.api.selectors.user.add_user import add_user
from src.api.models.user import User
from src.api.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
import redis.asyncio as redis
from src.api.dependencies.rate_limit import login_rate_limiter


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"]
)

@router.post("/register", response_model=TokenResponse, dependencies=[Depends(login_rate_limiter)])
async def register(
    request: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    existing_user = await get_user_by_email(request.email, db)
    if existing_user:
        raise HTTPException(
            status_code=400, 
            detail="Email already registered"
        )
    user = User(
        email=request.email.lower(),
        username=request.username,
        password_hash=auth_service.get_password_hash(request.password),
        provider="local",
    )
    user = await add_user(user, db)

    access_token = auth_service.create_access_token(data={"sub": user.email})

    return TokenResponse(access_token=access_token)
    
@router.post("/login", response_model=TokenResponse, dependencies=[Depends(login_rate_limiter)])
async def login(
    request: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await get_user_by_email(request.email, db)

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not auth_service.verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth_service.create_access_token(data={"sub": user.email})
    return TokenResponse(access_token=access_token)

@router.post("/token", response_model=TokenResponse, include_in_schema=False, dependencies=[Depends(login_rate_limiter)])
async def login_for_swagger(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    user = await get_user_by_email(form_data.username, db)

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if user.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not auth_service.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    access_token = auth_service.create_access_token(data={"sub": user.email})
    
    return TokenResponse(access_token=access_token)
    

@router.post("/logout")
async def logout(
    user: Annotated[User, Depends(get_current_user_required)],
    token: Annotated[str, Depends(oauth2_scheme)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    payload = auth_service.decode_access_token(token)
    if payload and "exp" in payload:
        from datetime import datetime, timezone
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        ttl = int((exp - datetime.now(timezone.utc)).total_seconds())
        if ttl > 0:
            await redis_client.setex(f"blacklist:{token}", ttl, "1")
    
    return {"message": "Successfully logged out"}
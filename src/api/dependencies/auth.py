from functools import lru_cache
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.api.services.auth_service import AuthService
from src.api.models.user import User
from src.api.dependencies.clients import get_db
from src.api.selectors.user.get_user import get_user_by_email
from typing import Optional, Annotated


@lru_cache()
def get_auth_service() -> AuthService:
    return AuthService()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login", 
    auto_error=False
)

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], 
    db: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> Optional[User]:
    if not token:
        return None
    payload = auth_service.decode_access_token(token)
    if not payload:
        return None
    user_email = payload.get("sub")
    if user_email is None:
        return None
    user = await get_user_by_email(user_email, db)
    return user
    
async def get_current_user_required(
    user: Annotated[Optional[User], Depends(get_current_user)],
) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user




from src.api.services.auth_service import AuthService
from functools import lru_cache
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import select
from src.api.services.auth_service import AuthService
from src.api.models.user import User

@lru_cache()
def get_auth_service() -> AuthService:
    return AuthService()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login", 
    auto_error=False
)

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
) -> Optional[User]:
    if not token:
        return None
    payload = auth_service.decode_access_token(token)
    if not payload:
        return None
    user_email = payload.get("sub")
    if user_email is None:
        return None
    statement = select(User).where(User.email == user_email)
    result = await db.exec(statement)
    user = result.first()
    return user
    
async def get_current_user_required(
    user: Optional[User] = Depends(get_current_user),
) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

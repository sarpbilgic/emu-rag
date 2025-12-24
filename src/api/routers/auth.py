from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_sso.sso.microsoft import MicrosoftSSO
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.settings import settings
from src.api.dependencies.clients import get_db
from src.api.services.auth_service import AuthService
from src.api.models.user import User
from src.api.selectors.user.get_user import get_user_by_email
from src.api.selectors.user.add_user import add_user
from src.api.dependencies.auth import get_auth_service
from typing import Annotated

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"]
)

microsoft_sso = MicrosoftSSO(
    client_id=settings.microsoft_client_id,
    client_secret=settings.microsoft_client_secret,
    tenant=settings.microsoft_tenant_id,
    redirect_uri=settings.microsoft_redirect_uri,
    allow_insecure_http=True
)

@router.get("/microsoft/login")
async def microsoft_login():
    with microsoft_sso:
        return await microsoft_sso.get_login_redirect()

@router.get("/microsoft/callback")
async def microsoft_callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    with microsoft_sso:
        user_data = await microsoft_sso.verify_and_process(request)
        if not user_data:
            raise HTTPException(status_code=401, detail="Microsoft login failed")
        if not user_data.email.lower().endswith("@emu.edu.tr"):
            raise HTTPException(status_code=403, detail="Only EMU students can login")
        
        user = await get_user_by_email(user_data.email, db)
        if not user:
            user = User(
                username=user_data.display_name or user_data.email.split("@")[0],
                email=user_data.email,
                provider="microsoft",
                provider_id=user_data.id,
                is_active=True
            )
            user = await add_user(user, db)
        access_token = auth_service.create_access_token(data={"sub": user.email})
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "email": user.email,
                "username": user.username,
            }
        }

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_sso.sso.microsoft import MicrosoftSSO
from sqlmodel.ext.asyncio.session import AsyncSession
import logging
import jwt
from typing import Annotated, Optional

from src.core.settings import settings
from src.api.dependencies.clients import get_db
from src.api.services.auth_service import AuthService
from src.api.selectors.user.get_or_create_user import get_or_create_user
from src.api.dependencies.auth import get_auth_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"]
)

microsoft_sso = MicrosoftSSO(
    client_id=settings.microsoft_client_id,
    client_secret=settings.microsoft_client_secret,
    tenant="common",
    redirect_uri=settings.microsoft_redirect_uri,
    allow_insecure_http=True,
    scope=["openid", "email", "profile"]
)


@router.get("/microsoft/login")
async def microsoft_login():
    """Initiate Microsoft OAuth login flow."""
    async with microsoft_sso:
        return await microsoft_sso.get_login_redirect()


@router.get("/microsoft/callback")
async def microsoft_callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    """Handle Microsoft OAuth callback."""
    try:
        async with microsoft_sso:
            user_data = await microsoft_sso.verify_and_process(request)
            
            if not user_data:
                logger.error("Microsoft SSO verification failed")
                raise HTTPException(
                    status_code=401, 
                    detail="Authentication failed: Unable to verify Microsoft account"
                )
            
            email: Optional[str] = None
            user_id: Optional[str] = None
            display_name: Optional[str] = None
            first_name: Optional[str] = None
            
            id_token = getattr(microsoft_sso, '_id_token', None)
            
            if id_token:
                try:
                    decoded_token = jwt.decode(id_token, options={"verify_signature": False})
                    email = auth_service.extract_email_from_token(decoded_token)
                    user_info = auth_service.extract_user_info_from_token(decoded_token)
                    user_id = user_info["user_id"]
                    display_name = user_info["display_name"]
                    first_name = user_info["first_name"]
                except jwt.DecodeError as e:
                    logger.warning(f"Failed to decode ID token: {e}")
            
            if not email:
                user_info = auth_service.extract_user_info_from_sso_user_data(user_data)
                email = user_info["email"]
                user_id = user_info["user_id"]
                display_name = user_info["display_name"]
                first_name = user_info["first_name"]
            
            if not email:
                logger.error("No email found in Microsoft SSO response")
                raise HTTPException(
                    status_code=400, 
                    detail="Email not provided by Microsoft account"
                )
            
            auth_service.validate_emu_email(email)
            
            user = await get_or_create_user(
                email=email,
                user_id=user_id,
                display_name=display_name,
                first_name=first_name,
                db=db
            )
            
            access_token = auth_service.create_access_token(data={"sub": user.email})
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "email": user.email,
                    "username": user.username,
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during Microsoft OAuth callback: {e}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during authentication. Please try again later."
        )

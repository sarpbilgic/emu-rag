from fastapi import Request
from typing import Optional
from src.api.models.user import User
from src.api.dependencies.auth import get_auth_service
from fastapi_limiter.depends import RateLimiter
from src.core.settings import settings


async def get_real_ip(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"

async def user_id_identifier(request: Request) -> str:
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        auth_service = get_auth_service()
        payload = auth_service.decode_access_token(token)
        if payload:
            user_email = payload.get("sub")
            if user_email:
                return f"user:{user_email}"
    ip = await get_real_ip(request)
    return f"ip:{ip}"

async def ip_identifier(request: Request) -> str:
    ip = await get_real_ip(request)
    return f"ip:{ip}"

anonymous_rag_rate_limiter = RateLimiter(
    times=10 if settings.env == "production" else 100,  
    seconds=3600,  
    identifier=ip_identifier
)

authenticated_rag_rate_limiter = RateLimiter(
    times=25 if settings.env == "production" else 100,  
    seconds=3600,  
    identifier=user_id_identifier
)

login_rate_limiter = RateLimiter(
    times=25,
    seconds=300,
    identifier=ip_identifier
)

general_rate_limiter = RateLimiter(
    times=100,
    seconds=3600,
    identifier=user_id_identifier
)
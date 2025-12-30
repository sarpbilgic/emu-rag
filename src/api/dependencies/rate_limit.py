from fastapi import Request
from typing import Optional
from src.api.models.user import User
from src.api.dependencies.auth import get_auth_service
from fastapi_limiter.depends import RateLimiter

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
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return f"ip:{forwarded_for.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"

async def ip_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return f"ip:{forwarded_for.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"

rag_rate_limiter = RateLimiter(
    times=7,  
    seconds=3600,  
    identifier=user_id_identifier
)

login_rate_limiter = RateLimiter(
    times=10,
    seconds=300,
    identifier=ip_identifier
)
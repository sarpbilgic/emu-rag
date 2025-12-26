from sqlmodel.ext.asyncio.session import AsyncSession
from typing import Optional
import logging

from src.api.models.user import User
from src.api.selectors.user.get_user import get_user_by_email
from src.api.selectors.user.add_user import add_user

logger = logging.getLogger(__name__)


async def get_or_create_user(
    email: str,
    user_id: Optional[str],
    display_name: Optional[str],
    first_name: Optional[str],
    db: AsyncSession
) -> User:
    user = await get_user_by_email(email, db)
    
    if not user:
        username = display_name or first_name or email.split("@")[0]
        
        user = User(
            username=username,
            email=email,
            provider="microsoft",
            provider_id=user_id,
            is_active=True
        )
        user = await add_user(user, db)
        logger.info(f"Created new user: {email}")
    
    return user


from sqlmodel import select
from src.api.models.user import User
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import Optional


async def get_user_by_email(email: str, db: AsyncSession) -> Optional[User]:
    email = email.lower()
    return await db.exec(select(User).where(User.email == email)).first()

async def get_user_by_id(id: int, db: AsyncSession) -> Optional[User]:
    return await db.exec(select(User).where(User.id == id)).first()


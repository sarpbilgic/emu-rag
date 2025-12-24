from src.api.models.user import User
from sqlmodel.ext.asyncio.session import AsyncSession

async def add_user(user: User, db: AsyncSession) -> User:
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
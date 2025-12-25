from sqlmodel.ext.asyncio.session import AsyncSession
from src.api.models.chat import ChatSession
from typing import Optional
import uuid

async def create_sessions(
    user_id: Optional[int],
    title: str,
    db: AsyncSession
) -> ChatSession:
    session = ChatSession(
        id = uuid.uuid4(),
        title = title,
        user_id = user_id,
        is_active = True,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session
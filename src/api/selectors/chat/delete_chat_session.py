from sqlmodel.ext.asyncio.session import AsyncSession
from src.api.models.chat import ChatSession
from typing import Optional
import uuid
from sqlmodel import delete

async def delete_chat_session(
    session_id: uuid.UUID,
    user_id: int,
    db: AsyncSession
) -> None:
    statement = delete(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id 
    )
    await db.execute(statement)
    await db.commit()

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.api.models.chat import ChatSession
from typing import Optional
import uuid

async def get_chat_session(
    session_id: uuid.UUID,
    user_id: Optional[int],
    db: AsyncSession
) -> Optional[ChatSession]:
    query = select(ChatSession).where(ChatSession.id == session_id)
    if user_id:
        query = query.where(ChatSession.user_id == user_id)
    
    result = await db.exec(query)
    return result.first()
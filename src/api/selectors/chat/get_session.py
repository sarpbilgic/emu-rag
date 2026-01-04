from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.api.models.chat import ChatSession
from typing import Optional, List
import uuid

async def get_chat_session_by_id(
    session_id: uuid.UUID,
    user_id: Optional[int],
    db: AsyncSession
) -> Optional[ChatSession]:
    query = select(ChatSession).where(ChatSession.id == session_id)
    result = await db.exec(query)
    session = result.first()
    if not session:
        return None
    if session.user_id is not None:
        if session.user_id != user_id or user_id is None:
            return None
    else:
        if user_id is not None:
            return None
    return session
    
    
async def get_chat_sessions(
    user_id: int,
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0
) -> List[ChatSession]:
    query = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .where(ChatSession.is_active == True) 
        .order_by(ChatSession.updated_at.desc()) 
        .limit(limit)
        .offset(offset)
    )
    result = await db.exec(query)
    return result.all()


import uuid
from typing import List
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.api.models.chat import ChatMessage

async def get_chat_messages_by_session(
    session_id: uuid.UUID,
    db: AsyncSession
) -> List[ChatMessage]:
    query = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.timestamp)
    )
    result = await db.exec(query)
    return result.all()
from sqlmodel.ext.asyncio.session import AsyncSession
from src.api.models.chat import ChatSession, ChatMessage, ChatMessageRole
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole
from typing import List
from datetime import datetime
from pytz import timezone

def llama_to_db_role(llama_role: MessageRole) -> ChatMessageRole:
    mapping = {
        MessageRole.USER: ChatMessageRole.USER,
        MessageRole.ASSISTANT: ChatMessageRole.ASSISTANT,
        MessageRole.SYSTEM: ChatMessageRole.SYSTEM,
    }
    return mapping.get(llama_role, ChatMessageRole.USER)

async def save_messages_to_db(
    session: ChatSession, 
    messages: List[LlamaChatMessage],
    db: AsyncSession
) -> List[ChatMessage]:
    db_messages = []
    now = datetime.now(timezone.utc)
    for msg in messages:
        db_message = ChatMessage(
            content=msg.content,
            role=llama_to_db_role(msg.role),
            timestamp=now,
            session_id=session.id,
        )
        db_messages.append(db_message)
        db.add(db_message)
    await db.commit()
    for msg in db_messages:
        await db.refresh(msg)
    return db_messages
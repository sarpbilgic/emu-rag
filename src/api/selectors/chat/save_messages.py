from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, delete
from src.api.models.chat import ChatSession, ChatMessage, ChatMessageRole
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole
from typing import List

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
    db: AsyncSession,
    replace_existing: bool = True
) -> List[ChatMessage]:
    if replace_existing:
        await db.exec(
            delete(ChatMessage).where(ChatMessage.session_id == session.id)
        )
        await db.commit()
    
    db_messages = []
    for i, msg in enumerate(messages):
        db_message = ChatMessage(
            content=str(msg.content),
            role=llama_to_db_role(msg.role),
            session_id=session.id,
        )
        db_messages.append(db_message)
        db.add(db_message)
    
    await db.commit()
    for msg in db_messages:
        await db.refresh(msg)
    return db_messages
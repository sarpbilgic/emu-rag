from fastapi import APIRouter, Depends, Query
from typing import Annotated, List
from src.api.models.user import User
from src.api.models.chat import ChatMessageRole
from src.api.dependencies.auth import get_current_user_required, get_current_user_optional
from src.api.dependencies.clients import get_db, get_chat_history_service
from sqlmodel.ext.asyncio.session import AsyncSession
from src.api.selectors.chat.get_session import get_chat_sessions
from src.api.schemas.session import ChatSessionList, ChatMessageRead
from src.api.services.chat_history_service import ChatHistoryService
from llama_index.core.llms import MessageRole
import uuid

router = APIRouter(
    prefix="/api/v1",
    tags=["Sessions"],
)

def _llama_role_to_chat_role(role: MessageRole) -> ChatMessageRole:
    mapping = {
        MessageRole.USER: ChatMessageRole.USER,
        MessageRole.ASSISTANT: ChatMessageRole.ASSISTANT,
        MessageRole.SYSTEM: ChatMessageRole.SYSTEM,
    }
    return mapping.get(role, ChatMessageRole.USER)

@router.get("/sessions", response_model=List[ChatSessionList])
async def list_sessions(
    user: Annotated[User, Depends(get_current_user_required)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(le=100)] = 20,
    offset: int = 0
):
    return await get_chat_sessions(
        user_id=user.id, 
        db=db, 
        limit=limit, 
        offset=offset
    )

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageRead])
async def get_messages(
    session_id: uuid.UUID,
    chat_history_service: Annotated[ChatHistoryService, Depends(get_chat_history_service)],
    user: Annotated[User, Depends(get_current_user_optional)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    messages = await chat_history_service.get_messages(
        session_id=session_id,
        user=user,
        db=db
    )
    return [
        ChatMessageRead(
            role=_llama_role_to_chat_role(msg.role),
            content=str(msg.content)
        )
        for msg in messages
    ]

    
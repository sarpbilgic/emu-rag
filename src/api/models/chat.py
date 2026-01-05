from sqlmodel import Field, SQLModel, Relationship
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
import uuid
from sqlalchemy import Text
from enum import Enum


if TYPE_CHECKING:
    from src.api.models.user import User

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class ChatMessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_sessions"
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(nullable=False)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", nullable=True)
    user: Optional["User"] = Relationship(back_populates="sessions")
    messages: List["ChatMessage"] = Relationship(back_populates="session", cascade_delete=True)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str = Field(sa_type=Text)
    role: ChatMessageRole = Field(index=True)
    timestamp: datetime = Field(default_factory=utc_now)
    session_id: uuid.UUID = Field(foreign_key="chat_sessions.id")
    session: ChatSession = Relationship(back_populates="messages")
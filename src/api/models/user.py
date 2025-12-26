from sqlmodel import Field, SQLModel, Relationship
from datetime import datetime, timezone
from pydantic import EmailStr
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.models.chat import ChatSession

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(nullable=False, index=True, unique=True)
    email: EmailStr = Field(index=True, unique=True)
    password_hash: Optional[str] = Field(default=None, nullable=True)
    is_active: bool = Field(default=True)
    provider: Optional[str] = Field(default="local", index=True)
    provider_id: Optional[str] = Field(default=None, index=True, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    sessions: List["ChatSession"] = Relationship(back_populates="user")
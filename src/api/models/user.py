from sqlmodel import Field, SQLModel, Relationship
from datetime import datetime
from pydantic import EmailStr
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.models.chat import ChatSession

class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(nullable=False, index=True, unique=True)
    email: EmailStr = Field(index=True, unique=True)
    password_hash: str = Field(nullable=False)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    sessions: List["ChatSession"] = Relationship(back_populates="user")
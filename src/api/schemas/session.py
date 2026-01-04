from pydantic import BaseModel
import uuid
from datetime import datetime
from src.api.models.chat import ChatMessageRole

class ChatSessionList(BaseModel):
    id: uuid.UUID
    title: str
    updated_at: datetime

    class Config:
        from_attributes = True

class ChatMessageRead(BaseModel):
    role: ChatMessageRole
    content: str

    class Config:
        from_attributes = True
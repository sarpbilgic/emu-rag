from __future__ import annotations
from typing import Optional, List
from llama_index.core.llms import ChatMessage, MessageRole
from sqlmodel.ext.asyncio.session import AsyncSession
from src.api.models.user import User
from src.api.models.chat import ChatSession
from src.api.selectors.chat.get_session import get_chat_session_by_id
from src.api.selectors.chat.create_session import create_sessions
from src.api.selectors.chat.save_messages import save_messages_to_db
from src.api.selectors.chat.get_messages import get_chat_messages_by_session
import uuid
import logging
from src.core.settings import settings

logger = logging.getLogger(__name__)


class ChatHistoryService:
    def __init__(self, redis_client: "RedisClient"):
        self.redis_store = redis_client.get_chat_store()
        self.anonymous_ttl = getattr(settings, "anonymous_chat_ttl", 86400)
        self.authenticated_ttl = getattr(settings, "authenticated_chat_ttl", None)

    def _get_redis_key(self, session_id: uuid.UUID, user: Optional[User]) -> str:
        if user:
            return f"chat:user:{user.id}:session:{session_id}"
        return f"chat:anonymous:session:{session_id}"

    async def get_messages(
        self,
        session_id: uuid.UUID,
        user: Optional[User],
        db: Optional[AsyncSession] = None
    ) -> List[ChatMessage]:
        try:
            key = self._get_redis_key(session_id, user)
            messages = await self.redis_store.aget_messages(key)
            if messages:
                return messages
            if db:
                session = await get_chat_session_by_id(session_id, user.id if user else None, db)
                if not session:
                    return []
                db_messages = await get_chat_messages_by_session(session_id, db)
                if db_messages:
                    llama_messages = [
                        ChatMessage(
                            role=message.role, 
                            content=message.content) 
                            for message in db_messages
                        ]
                    await self.redis_store.aset_messages(key, llama_messages)
                    return llama_messages

            return []
        except Exception as e:
            logger.warning(f"Failed to get messages from Redis: {e}. Returning empty list.")
            return []

    async def add_message(
        self,
        session_id: uuid.UUID,
        message: ChatMessage,
        user: Optional[User]
    ) -> None:
        try:
            key = self._get_redis_key(session_id, user)
            await self.redis_store.aadd_message(key, message)
        except Exception as e:
            logger.warning(f"Failed to add message to Redis: {e}. Message not stored.")

    async def set_messages(
        self,
        session_id: uuid.UUID,
        messages: List[ChatMessage],
        user: Optional[User]
    ) -> None:
        try:
            key = self._get_redis_key(session_id, user)
            await self.redis_store.aset_messages(key, messages)
        except Exception as e:
            logger.warning(f"Failed to set messages in Redis: {e}. Messages not stored.")

    async def delete_session(
        self,
        session_id: uuid.UUID,
        user: Optional[User]
    ) -> Optional[List[ChatMessage]]:
        try:
            key = self._get_redis_key(session_id, user)
            return await self.redis_store.adelete_messages(key)
        except Exception as e:
            logger.warning(f"Failed to delete session from Redis: {e}.")
            return None



    async def sync_to_postgres(
        self,
        session_id: uuid.UUID,
        user: User,
        db: AsyncSession,
        title: Optional[str] = None
    ) -> Optional[ChatSession]:
        messages = await self.get_messages(session_id, user, db)
        
        if not messages:
            return None
        
        db_session = await get_chat_session_by_id(session_id, user.id, db)
        
        if not db_session:
            if not title:
                first_user_msg = next(
                    (m for m in messages if m.role == MessageRole.USER),
                    None
                )
                title = (first_user_msg.content[:100] if first_user_msg 
                         else "Chat Session")
            
            db_session = await create_sessions(
                user_id=user.id,
                title=title,
                db=db,
                session_id=session_id  
            )
        
        await save_messages_to_db(
            session=db_session,
            messages=messages,
            db=db,
            replace_existing=True  
        )
        
        return db_session

    async def migrate_anonymous_to_user(
        self,
        session_id: uuid.UUID,
        user: User,
        db: AsyncSession
    ) -> Optional[ChatSession]:
        try:
            anonymous_key = f"chat:anonymous:session:{session_id}"
            messages = await self.redis_store.aget_messages(anonymous_key)
            
            if not messages:
                return None
            
            user_key = self._get_redis_key(session_id, user)
            await self.redis_store.aset_messages(user_key, messages)
            
            db_session = await self.sync_to_postgres(session_id, user, db)
            
            await self.redis_store.adelete_messages(anonymous_key)
            
            return db_session
        except Exception as e:
            logger.warning(f"Failed to migrate anonymous session to user in Redis: {e}.")
            return None

    
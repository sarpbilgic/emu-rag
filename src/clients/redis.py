from llama_index.storage.chat_store.redis import RedisChatStore
from src.core.settings import settings

class RedisClient:
    def __init__(self):
        self.chat_store = RedisChatStore(
            redis_url=settings.redis_url,
            ttl=86400,
        )

    def get_chat_store(self) -> RedisChatStore:
        return self.chat_store
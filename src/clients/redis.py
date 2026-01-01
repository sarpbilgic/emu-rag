from llama_index.storage.chat_store.redis import RedisChatStore
from src.core.settings import settings
import redis.asyncio as redis

class RedisClient:
    def __init__(self):
        self.chat_store = RedisChatStore(
            redis_url=settings.redis_url,
            ttl=86400,
        )
        self.redis = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            encoding="utf-8"
        )

    def get_chat_store(self) -> RedisChatStore:
        return self.chat_store

    def get_redis(self) -> redis.Redis:
        return self.redis
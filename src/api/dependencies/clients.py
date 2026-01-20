from src.clients.llm import LLMClient
from src.clients.embedding_client import EmbeddingClient
from src.clients.sparse_embedding_client import SparseEmbeddingClient
from src.clients.qdrant import QdrantClientManager
from src.clients.redis import RedisClient
from src.clients.reranker_client import RerankerClient
from src.clients.postgres import async_session
from src.api.services.rag_service import RAGService
from src.api.services.chat_history_service import ChatHistoryService
from src.api.services.reranker_service import RerankerService
from src.core.settings import settings
from functools import lru_cache
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import AsyncGenerator, List
import redis.asyncio as redis

@lru_cache()
def get_llm_client() -> LLMClient:
    return LLMClient()

@lru_cache()
def get_embedding_client() -> EmbeddingClient:
    return EmbeddingClient()

@lru_cache()
def get_sparse_embedding_client() -> SparseEmbeddingClient:
    return SparseEmbeddingClient()

@lru_cache()
def get_qdrant_client() -> QdrantClientManager:
    qdrant = QdrantClientManager()
    sparse_client = get_sparse_embedding_client()

    def sparse_embed_fn(texts: List[str]):
        return sparse_client.embed_documents(texts)
    
    qdrant.set_sparse_embed_fn(sparse_embed_fn)
    return qdrant

@lru_cache()
def get_redis_client() -> RedisClient:
    return RedisClient()

@lru_cache()
def get_reranker_client() -> RerankerClient | None:
    """Get reranker client if enabled."""
    if not settings.reranker_enabled:
        return None
    return RerankerClient(model_name=settings.reranker_model)

@lru_cache()
def get_reranker_service() -> RerankerService:
    return RerankerService(get_reranker_client())

@lru_cache()
def get_redis() -> redis.Redis:
    return get_redis_client().get_redis()
    
@lru_cache()
def get_chat_history_service() -> ChatHistoryService:
    return ChatHistoryService(get_redis_client())

class RAGClients:
    def __init__(self):
        self.llm = get_llm_client()
        self.embeddings = get_embedding_client()
        self.qdrant = get_qdrant_client()
        self.redis = get_redis_client()
        self.chat_history = get_chat_history_service()
        self.reranker = get_reranker_service()

@lru_cache()
def get_rag_clients() -> RAGClients:
    return RAGClients()

@lru_cache()
def get_rag_service() -> RAGService:
    return RAGService(get_rag_clients())

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
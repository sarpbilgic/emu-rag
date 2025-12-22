"""
FastAPI Dependency Injection for clients.
Use with: Depends(get_llm_client), Depends(get_embedding_client), etc.
"""
from functools import lru_cache
from src.clients.llm import LLMClient
from src.clients.embedding_client import EmbeddingClient
from src.clients.qdrant import QdrantClientManager
from src.api.services.rag_service import RAGService
from src.clients.postgres import async_session
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import AsyncGenerator

@lru_cache()
def get_llm_client() -> LLMClient:
    return LLMClient()


@lru_cache()
def get_embedding_client() -> EmbeddingClient:
    return EmbeddingClient()


@lru_cache()
def get_qdrant_client() -> QdrantClientManager:
    return QdrantClientManager()



class RAGClients:
    def __init__(self):
        self.llm = get_llm_client()
        self.embeddings = get_embedding_client()
        self.qdrant = get_qdrant_client()


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
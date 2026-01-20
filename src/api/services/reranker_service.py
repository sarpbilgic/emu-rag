from __future__ import annotations
from typing import TYPE_CHECKING, TypeVar, Generic
from src.api.schemas.rag import RerankResult
from src.core.settings import settings

if TYPE_CHECKING:
    from src.clients.reranker_client import RerankerClient

T = TypeVar('T')


class RerankerService:
    def __init__(self, client: "RerankerClient | None"):
        self.client = client
        self.enabled = client is not None and settings.reranker_enabled
    
    def rerank_texts(self, query: str, texts: list[str], top_k: int = 5) -> list[RerankResult]:
        if not self.enabled or not texts:
            return [RerankResult(text=t, score=1.0, index=i) for i, t in enumerate(texts[:top_k])]
        
        results = list(self.client.rerank(query, texts))
        
        return sorted(
            [RerankResult(text=r.document, score=r.relevance_score, index=i) for i, r in enumerate(results)],
            key=lambda x: x.score,
            reverse=True
        )[:top_k]
    
    def rerank_items(self, query: str, items: list[T], key: callable, top_k: int = 5) -> list[T]:
        if not self.enabled or not items:
            return items[:top_k]
        
        texts = [key(item) for item in items]
        results = list(self.client.rerank(query, texts))

        scored = sorted(enumerate(results), key=lambda x: x[1].relevance_score, reverse=True)
        return [items[i] for i, _ in scored[:top_k]]


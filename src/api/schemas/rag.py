from pydantic import BaseModel, Field
from typing import List, Optional
import uuid


class SourceDocument(BaseModel):
    rank: int
    source: str
    title: Optional[str] = None
    article: Optional[str] = None


class RerankResult(BaseModel):
    text: str
    score: float
    index: int  


class RetrievalResult(BaseModel):
    context: str = Field(..., description="Clean text for LLM")
    sources: List[SourceDocument] = Field(default_factory=list)


class RAGResponse(BaseModel):
    answer: str
    sources: List[SourceDocument]
    query: str
    has_answer: bool = True
    session_id: uuid.UUID
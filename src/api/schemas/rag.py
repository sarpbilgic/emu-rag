from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class SourceDocument(BaseModel):
    rank: int
    source: str
    title: Optional[str] = None
    article: Optional[str] = None

class RetrievalResult(BaseModel):
    context: str = Field(..., description= "Clean text for LLM to use")
    sources: List[SourceDocument] = Field(default_factory=list, description= "Source metadata for user")

class RAGResponse(BaseModel):
    answer: str
    sources: List[SourceDocument]
    query: str
    has_answer: bool = True
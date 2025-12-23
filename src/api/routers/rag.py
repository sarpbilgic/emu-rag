from fastapi import APIRouter, Depends, HTTPException
from typing import TYPE_CHECKING
from src.api.dependencies.clients import get_rag_service
from src.api.schemas.rag import RAGResponse

if TYPE_CHECKING:
    from src.api.services.rag_service import RAGService

router = APIRouter(
    prefix="/api/v1/rag",
    tags=["RAG"],
)

@router.post("/ask", response_model=RAGResponse)
async def ask(query: str, rag_service: "RAGService" = Depends(get_rag_service)):
    return await rag_service.generate_response(query)

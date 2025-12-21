from fastapi import APIRouter, Depends, HTTPException
from typing import TYPE_CHECKING
from src.core.dependencies import get_rag_service
from src.schemas.rag import RAGResponse

if TYPE_CHECKING:
    from src.services.rag_service import RAGService

router = APIRouter()

@router.post("/rag")
async def rag(query: str, rag_service: "RAGService" = Depends(get_rag_service)) -> RAGResponse:
    return rag_service.generate_response(query)

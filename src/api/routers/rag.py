from fastapi import APIRouter, Depends, Header, Request
from typing import TYPE_CHECKING, Annotated, Optional
import uuid
from sqlmodel.ext.asyncio.session import AsyncSession
from src.api.dependencies.clients import get_rag_service, get_db
from src.api.schemas.rag import RAGResponse
from src.api.dependencies.auth import get_current_user_optional
from src.api.models.user import User
from src.api.dependencies.rate_limit import rag_rate_limiter

if TYPE_CHECKING:
    from src.api.services.rag_service import RAGService

router = APIRouter(
    prefix="/api/v1/rag",
    tags=["RAG"],
)

@router.post(
    "/ask",
     response_model=RAGResponse,
     dependencies=[
        Depends(rag_rate_limiter)
     ]
)
async def ask(
    request: Request,
    query: str,
    rag_service: Annotated["RAGService", Depends(get_rag_service)],
    user: Annotated[Optional[User], Depends(get_current_user_optional)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_session_id: Annotated[Optional[str], Header()] = None,
) -> RAGResponse:
    request.state.is_authenticated = user is not None
    session_id = uuid.UUID(x_session_id) if x_session_id else uuid.uuid4()
    return await rag_service.generate_response(query, session_id, user, db)

from fastapi import APIRouter, Depends
from src.api.dependencies.auth import get_current_user_required
from src.api.models.user import User
from src.api.schemas.user import UserRead
from typing import Annotated
from src.api.dependencies.rate_limit import general_rate_limiter

router = APIRouter(
    prefix="/api/v1/user",
    tags=["user"],
)
@router.get("/me", response_model=UserRead, dependencies=[Depends(general_rate_limiter)])
async def get_me(
    user: Annotated[User, Depends(get_current_user_required)],
):
    return user
from fastapi import APIRouter, Depends
from src.api.dependencies.auth import get_current_user_required
from src.api.models.user import User
from src.api.schemas.user import UserRead
from typing import Annotated

router = APIRouter(
    prefix="/api/v1/user",
    tags=["user"],
)
@router.get("/me", response_model=UserRead)
async def get_me(
    user: Annotated[User, Depends(get_current_user_required)],
):
    return user
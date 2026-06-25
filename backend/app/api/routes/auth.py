from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.models.auth import CurrentUser

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get(
    "/me",
    response_model=CurrentUser,
    responses={
        401: {
            "description": "Authentication credentials are missing, invalid, or expired."
        }
    },
)
def get_my_profile(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Return the authenticated user's profile."""
    return current_user
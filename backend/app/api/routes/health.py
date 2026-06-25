import logging

from fastapi import APIRouter

from app.core.config import get_settings
from app.models.common import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return the current health status of the API."""
    logger.info("Health check requested")

    settings = get_settings()

    return HealthResponse(
        status="ok",
        service="compliance-rag-api",
        environment=settings.app_env,
    )
import logging

from fastapi import APIRouter

from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return the current health status of the API."""
    logger.info("Health check requested")

    settings = get_settings()

    return {
        "status": "ok",
        "service": "compliance-rag-api",
        "environment": settings.app_env,
    }
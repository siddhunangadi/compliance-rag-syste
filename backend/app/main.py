import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging()

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run application startup and shutdown logic."""
    logger.info(
        "%s started in %s mode",
        settings.app_name,
        settings.app_env,
    )

    yield

    logger.info("%s is shutting down", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend API for the Compliance RAG System.",
    lifespan=lifespan,
)

app.include_router(health_router)
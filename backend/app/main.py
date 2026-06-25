import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
register_exception_handlers(app)
import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.services.ingestion_job_service import ingestion_job_service
from app.services.ingestion_worker_service import ingestion_worker_service

configure_logging()

logger = logging.getLogger(__name__)
settings = get_settings()


async def recover_interrupted_ingestion_jobs() -> None:
    """
    Requeue and process jobs left queued or stale-processing after a restart.

    Startup must not fail if recovery has an issue; the API should still boot.
    """
    try:
        recoverable_jobs = await asyncio.to_thread(
            ingestion_job_service.get_recoverable_jobs
        )

        if not recoverable_jobs:
            logger.info("No interrupted ingestion jobs found during startup.")
            return

        logger.warning(
            "Recovering %s interrupted ingestion job(s).",
            len(recoverable_jobs),
        )

        for job in recoverable_jobs:
            job_id = job["id"]
            document_id = job["document_id"]
            user_id = job["user_id"]

            try:
                await asyncio.to_thread(
                    ingestion_job_service.requeue_job_for_recovery,
                    job_id=job_id,
                    user_id=user_id,
                )

                asyncio.create_task(
                    asyncio.to_thread(
                        ingestion_worker_service.process_job,
                        job_id=job_id,
                        document_id=document_id,
                        user_id=user_id,
                    )
                )

                logger.info(
                    "Recovery queued: job_id=%s document_id=%s user_id=%s",
                    job_id,
                    document_id,
                    user_id,
                )

            except Exception:
                logger.exception(
                    "Could not recover ingestion job: job_id=%s "
                    "document_id=%s user_id=%s",
                    job_id,
                    document_id,
                    user_id,
                )

    except Exception:
        logger.exception(
            "Could not inspect interrupted ingestion jobs during startup."
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run application startup and shutdown logic."""
    logger.info(
        "%s started in %s mode",
        settings.app_name,
        settings.app_env,
    )

    await recover_interrupted_ingestion_jobs()

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
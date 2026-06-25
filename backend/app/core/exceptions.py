import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.models.common import ErrorResponse

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register application-wide exception handlers."""

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Return a safe response for unexpected server errors."""
        logger.exception(
            "Unhandled error while processing %s %s",
            request.method,
            request.url.path,
        )

        error_response = ErrorResponse(
            detail="An unexpected internal server error occurred.",
            status_code=500,
        )

        return JSONResponse(
            status_code=500,
            content=error_response.model_dump(),
        )
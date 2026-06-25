from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response returned by the health-check endpoint."""

    status: str
    service: str
    environment: str


class ErrorResponse(BaseModel):
    """Standard error response returned by the API."""

    detail: str
    status_code: int
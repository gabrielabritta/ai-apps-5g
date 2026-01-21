"""Pydantic models used across the FastAPI server."""
from pydantic import BaseModel


class InferenceRequest(BaseModel):
    """Model for inference requests."""

    query: str
    user_id: str
    session_id: str
    search_db: bool = True
    use_history: bool = True
    search_urls: bool = False
    n_chunks: int = 3


class InferenceResponse(BaseModel):
    """Model for inference responses."""

    answer: str
    history_sources: list


class HealthResponse(BaseModel):
    """Model for health check response."""

    status: str
    message: str


class ServiceRequest(BaseModel):
    """Model for service lifecycle requests."""

    session_id: str
    user_id: str


class ServiceResponse(BaseModel):
    """Model for service lifecycle responses."""

    status: str
    message: str
    active_sessions_count: int

"""Health + Prometheus-friendly readiness."""

from fastapi import APIRouter

from app.models import HealthStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    """Service health check."""
    return HealthStatus(status="healthy")

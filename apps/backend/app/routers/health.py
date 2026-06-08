"""Standard health probes: ``/health/live`` + ``/health/ready``.

Shape-parity with eai-nano's ``eai.health`` factory **without** taking the eai-core
dependency — fleet-mgr keeps its minimal footprint (fastapi/uvicorn/httpx2/pydantic). The
external contract (paths, ``alive``/``ready``/``not_ready`` vocab, response schema) is
identical, so every EAI service probes the same way and k8s can gate uniformly.

fleet-mgr is a **stateless read-through over Prometheus** (no DB, no startup gate), so it is
ready the moment it serves; per-dependency detail (Prometheus reachable?) is telemetry, not a
probe trigger. Liveness is always 200 while the process serves.
"""

from enum import StrEnum

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthStatus(StrEnum):
    ALIVE = "alive"
    READY = "ready"
    NOT_READY = "not_ready"


class Liveness(BaseModel):
    """Response body: GET /health/live — the process is up."""

    status: HealthStatus = HealthStatus.ALIVE


class Readiness(BaseModel):
    """Response body: GET /health/ready — ready to receive traffic (or why not)."""

    status: HealthStatus
    reason: str | None = None


@router.get("/health/live", response_model=Liveness)
def live() -> Liveness:
    return Liveness(status=HealthStatus.ALIVE)


@router.get("/health/ready", response_model=Readiness)
def ready() -> Readiness:
    return Readiness(status=HealthStatus.READY)

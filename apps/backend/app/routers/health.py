"""Standard ``/health/live`` + ``/health/ready`` probes, from the shared ``eai.health`` factory.

Standardized across every EAI service via ``eai.health`` (parity with eai-nano + eai-catalog);
the router shape, status codes, and response schema are shared, so k8s gates uniformly and only
the readiness predicate is app-specific.

fleet-mgr is a **stateless read-through over Prometheus** (no DB, no startup gate), so it is
ready the moment it serves; per-dependency detail (Prometheus reachable?) is the ``/metrics``
telemetry, never a probe trigger. Liveness is always 200 while the process serves.
"""

from eai.health import build_health_router


async def _ready() -> tuple[bool, str | None]:
    """Readiness: fleet-mgr is ready as soon as it serves (stateless read-through)."""
    return True, None


router = build_health_router(_ready)

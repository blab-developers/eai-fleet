"""fleet-mgr — central fleet manager for the eai-nano Jetson fleet.

A small FastAPI service deployed on the eai-infra server (NOT on individual nanos).
It serves the fleet view, **derived** from central Prometheus (Spec 008): online/offline
from KubeEdge node status (kube-state-metrics) and telemetry from the nano agents'
remote_written ``eai_inference_*`` series. It holds no device state — no database, no
heartbeat ingest. Time-series dashboards live in the central Grafana (metrics role); the
native frontend (apps/frontend) is the live fleet view + the image-set control.
"""

from fastapi import FastAPI

from app.config import settings
from app.routers import fleet, health


def create_app() -> FastAPI:
    # generate_unique_id_function = route.name → clean OpenAPI operationIds
    # (listDevices, setInferenceImage) so the generated frontend SDK names are
    # tidy, not listDevicesApiFleetDevicesGet (AGENTS.md frontend↔backend types).
    app = FastAPI(
        title="fleet-mgr",
        version="0.1.0",
        generate_unique_id_function=lambda route: route.name,
    )
    app.include_router(health.router)
    app.include_router(fleet.router)
    return app


app = create_app()


def run() -> None:
    """Console entrypoint (`fleet-mgr`). Binds 0.0.0.0 for containerized deployment."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    run()

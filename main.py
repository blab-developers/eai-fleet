"""fleet-mgr — central fleet manager for the eai-nano Jetson fleet.

A small FastAPI service deployed on the eai-infra server (NOT on individual nanos).
It serves the fleet view, **derived** from central Prometheus (Spec 008): online/offline
from KubeEdge node status (kube-state-metrics) and telemetry from the nano agents'
remote_written ``eai_inference_*`` series. It holds no device state — no database, no
heartbeat ingest. Dashboards live in the paired Grafana container.
"""

from fastapi import FastAPI

from config import settings
from routers import fleet, health


def create_app() -> FastAPI:
    app = FastAPI(title="fleet-mgr", version="0.1.0")
    app.include_router(health.router)
    app.include_router(fleet.router)
    return app


app = create_app()


def run() -> None:
    """Console entrypoint (`fleet-mgr`). Binds 0.0.0.0 for containerized deployment."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.fleet_port)


if __name__ == "__main__":
    run()

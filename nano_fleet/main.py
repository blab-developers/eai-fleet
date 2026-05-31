"""nano-fleet — central fleet manager for the eai-nano Jetson fleet.

A small FastAPI service deployed on the eai-infra server (NOT on individual nanos).
It holds the device registry, ingests heartbeats from nanos, and serves the fleet view.
Liveness can be cross-checked against KubeEdge k8s Node status; metrics live in
Prometheus/Grafana; recordings (optional) catalog into eai_core.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .database import init_db
from .routers import fleet, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="fleet-mgr", version="0.1.0", lifespan=lifespan)
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

"""Fleet view — DERIVED from KubeEdge node status + Prometheus (Spec 008).

There is no heartbeat ingest anymore: the nano pushes no device state. Online/offline
comes from KubeEdge node status (kube-state-metrics) and telemetry from the nano agents'
remote_written ``eai_inference_*`` series, both read from central Prometheus.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from config import settings
from models import FleetView
from prometheus_query import PrometheusClient, PrometheusUnavailable, build_fleet_view

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


def get_prometheus() -> PrometheusClient:
    """FastAPI dependency: a client for the central Prometheus."""
    return PrometheusClient(settings.prometheus_url, settings.prometheus_timeout_s)


PrometheusDep = Annotated[PrometheusClient, Depends(get_prometheus)]


@router.get("/devices", response_model=FleetView)
def list_devices(prometheus: PrometheusDep) -> FleetView:
    """The whole fleet, derived from node status + inference telemetry."""
    try:
        return build_fleet_view(prometheus)
    except PrometheusUnavailable as e:
        # The view is never on the data path; if central is down we can't derive it.
        raise HTTPException(status_code=502, detail=str(e)) from e

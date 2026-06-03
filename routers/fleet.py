"""Fleet view — DERIVED from KubeEdge node status + Prometheus (Spec 008).

There is no heartbeat ingest anymore: the nano pushes no device state. Online/offline
comes from KubeEdge node status (kube-state-metrics) and telemetry from the nano agents'
remote_written ``eai_inference_*`` series, both read from central Prometheus.

The image-set route (``POST /devices/{id}/inference/image``) is the one mutating
endpoint — it patches the inference DaemonSet so a Nano picks up a different image
version. See its docstring for the v1 "fleet-wide under per-device shape" caveat.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from config import settings
from k8s_client import K8sClient, KubernetesUnavailable
from models import (
    FleetView,
    ImageSetScope,
    InferenceImageRequest,
    InferenceImageResponse,
)
from prometheus_query import PrometheusClient, PrometheusUnavailable, build_fleet_view

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


def get_prometheus() -> PrometheusClient:
    """FastAPI dependency: a client for the central Prometheus."""
    return PrometheusClient(settings.prometheus_url, settings.prometheus_timeout_s)


def get_k8s() -> K8sClient:
    """FastAPI dependency: an in-cluster k8s API client.

    Construction reads the SA token + CA from disk, so a missing mount surfaces
    here as ``KubernetesUnavailable`` → HTTP 502 from the route, not a startup
    crash. The read path (``GET /devices``) doesn't take this dep, so the
    service stays up even when the mutating endpoint is misconfigured.
    """
    return K8sClient()


PrometheusDep = Annotated[PrometheusClient, Depends(get_prometheus)]
K8sDep = Annotated[K8sClient, Depends(get_k8s)]


@router.get("/devices", response_model=FleetView)
def list_devices(prometheus: PrometheusDep) -> FleetView:
    """The whole fleet, derived from node status + inference telemetry."""
    try:
        return build_fleet_view(prometheus)
    except PrometheusUnavailable as e:
        # The view is never on the data path; if central is down we can't derive it.
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post(
    "/devices/{device_id}/inference/image",
    response_model=InferenceImageResponse,
)
def set_inference_image(
    device_id: str,
    request: InferenceImageRequest,
    prometheus: PrometheusDep,
    k8s: K8sDep,
) -> InferenceImageResponse:
    """Set the inference container image so a Nano picks it up on the next pod cycle.

    v1 — fleet-wide behind a per-device shape.
    The inference workload is a single fleet-wide DaemonSet
    (``eai-nano-inference``) so patching its image changes every Nano in the
    fleet, not just ``device_id``. The endpoint still takes ``device_id`` so
    the frontend contract is stable when per-device targeting graduates (to a
    per-Nano Deployment or DS overlay); the response's ``scope`` field stays
    ``"fleet-wide"`` until then.

    Errors:
      404 — ``device_id`` is not in the current fleet view. Stops typos from
            triggering a fleet-wide image swap from the wrong UI button.
      502 — the central Prometheus query (used to validate ``device_id``) or
            the k8s PATCH itself failed.
    """
    try:
        view = build_fleet_view(prometheus)
    except PrometheusUnavailable as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    if device_id not in {d.device_id for d in view.devices}:
        raise HTTPException(status_code=404, detail=f"device {device_id!r} not in fleet")

    try:
        k8s.patch_daemonset_image(
            namespace=settings.inference_namespace,
            name=settings.inference_daemonset,
            container=settings.inference_container,
            image=request.image,
        )
    except KubernetesUnavailable as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return InferenceImageResponse(
        device_id=device_id,
        image=request.image,
        scope=ImageSetScope.FLEET_WIDE,
        note=(
            f"Inference DaemonSet {settings.inference_namespace}/"
            f"{settings.inference_daemonset} patched. Today this updates every "
            "Nano in the fleet (Spec 008 demo scope); true per-device targeting "
            "lands with the per-Nano overlay."
        ),
    )

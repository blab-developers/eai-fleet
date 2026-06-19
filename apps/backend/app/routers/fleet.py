"""Fleet view — DERIVED from KubeEdge node status + Prometheus (Spec 008).

There is no heartbeat ingest anymore: the nano pushes no device state. Online/offline
comes from KubeEdge node status (kube-state-metrics) and telemetry from the nano agents'
remote_written ``eai_inference_*`` series, both read from central Prometheus.

The image-set route (``POST /devices/{id}/inference/image``) is the one mutating
endpoint — it patches the inference DaemonSet so a Nano picks up a different image
version. See its docstring for the v1 "fleet-wide under per-device shape" caveat.
"""

from typing import Annotated

import httpx2
from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.demo import with_demo_when_empty
from app.k8s import K8sClient, KubernetesUnavailable
from app.model_deploy import ModelDeployer
from app.models import (
    FleetView,
    ImageSetScope,
    InferenceImageRequest,
    InferenceImageResponse,
    ModelDeployRequest,
    ModelDeployResponse,
)
from app.prometheus import PrometheusClient, PrometheusUnavailable, build_fleet_view

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


def _assert_device_exists(device_id: str, prometheus: PrometheusClient) -> None:
    try:
        view = build_fleet_view(prometheus)
    except PrometheusUnavailable as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    if device_id not in {d.device_id for d in view.devices}:
        raise HTTPException(status_code=404, detail=f"device {device_id!r} not in fleet")


@router.get("/devices", response_model=FleetView)
def list_devices(prometheus: PrometheusDep) -> FleetView:
    """The whole fleet, derived from node status + inference telemetry.

    When ``EAI_FLEET_DEMO_MODE`` is set AND the real derived fleet is empty, canned demo devices
    are injected (each ``demo=True``); the frontend's per-browser toggle shows/hides them
    (frontend calls the shots). In production (demo off) this is a pure derived view.
    """
    try:
        return with_demo_when_empty(build_fleet_view(prometheus), settings.demo_mode)
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
    _assert_device_exists(device_id, prometheus)

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


@router.post(
    "/devices/{device_id}/models/{model_version_id}/deploy",
    response_model=ModelDeployResponse,
)
def deploy_model_package(
    device_id: str,
    model_version_id: str,
    request: ModelDeployRequest,
    prometheus: PrometheusDep,
) -> ModelDeployResponse:
    """Fetch a catalog model package into fleet's cache, then push it to one nano backend."""
    _assert_device_exists(device_id, prometheus)
    deployer = ModelDeployer(
        catalog_url=settings.catalog_url,
        catalog_token=settings.catalog_token,
        cache_dir=settings.model_cache_dir,
        timeout_s=settings.model_deploy_timeout_s,
    )
    try:
        cached = deployer.cache_package(model_version_id)
        installed = deployer.push_to_nano(cached, request.nano_base_url, request.nano_token)
    except (httpx2.HTTPError, ValueError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return ModelDeployResponse(
        device_id=device_id,
        model_version_id=model_version_id,
        model_id=cached.manifest.model_id,
        cached_package=str(cached.path),
        package_sha256=cached.sha256,
        nano_model_id=installed.model_id,
        scope=ImageSetScope.DEVICE,
    )

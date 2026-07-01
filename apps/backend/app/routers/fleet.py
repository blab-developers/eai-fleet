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

from app.catalog import CatalogClient, CatalogUnavailable
from app.config import settings
from app.demo import with_demo_when_empty
from app.k8s import K8sClient, KubernetesUnavailable
from app.model_deploy import ModelDeployer
from app.models import (
    FleetView,
    ImageSetScope,
    InferenceImageInfo,
    InferenceImageRequest,
    InferenceImageResponse,
    InferenceRestartResponse,
    InferenceRollbackResponse,
    ModelDeployRequest,
    ModelDeployResponse,
    ModelVersionView,
    RecordingsPullRequest,
    RecordingsPullResponse,
)
from app.prometheus import PrometheusClient, PrometheusUnavailable, build_fleet_view
from app.recordings_pull import RecordingsPuller

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


def get_prometheus() -> PrometheusClient:
    """FastAPI dependency: a client for the central Prometheus."""
    return PrometheusClient(settings.prometheus_url, settings.prometheus_timeout_s)


def get_catalog() -> CatalogClient:
    """FastAPI dependency: a read client for the central eai-catalog."""
    return CatalogClient(
        settings.catalog_url,
        settings.catalog_token,
        settings.model_deploy_timeout_s,
    )


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
CatalogDep = Annotated[CatalogClient, Depends(get_catalog)]


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


@router.get("/inference/image", response_model=InferenceImageInfo)
def get_inference_image(k8s: K8sDep) -> InferenceImageInfo:
    """The image the inference DaemonSet is currently running (the fleet's running version).

    Read live from k8s (the fleet keeps no state). Fleet-wide in v1 — one DaemonSet,
    one image. Kept off the derived ``GET /devices`` path so that read stays k8s-free.

    Errors: 502 — the k8s GET failed (API unreachable, DaemonSet missing).
    """
    try:
        image = k8s.get_daemonset_image(
            namespace=settings.inference_namespace,
            name=settings.inference_daemonset,
            container=settings.inference_container,
        )
    except KubernetesUnavailable as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return InferenceImageInfo(
        image=image,
        namespace=settings.inference_namespace,
        daemonset=settings.inference_daemonset,
        container=settings.inference_container,
        scope=ImageSetScope.FLEET_WIDE,
    )


@router.post(
    "/devices/{device_id}/inference/restart",
    response_model=InferenceRestartResponse,
)
def restart_inference(
    device_id: str,
    prometheus: PrometheusDep,
    k8s: K8sDep,
) -> InferenceRestartResponse:
    """Roll the inference pods (``kubectl rollout restart`` on the DaemonSet).

    v1 fleet-wide behind a per-device shape, same as set-image: the restart hits every
    Nano the DaemonSet runs on. ``device_id`` is validated so a typo can't trigger a
    fleet-wide restart from the wrong row.

    Errors: 404 — ``device_id`` not in the fleet view; 502 — Prometheus (device check)
    or the k8s PATCH failed.
    """
    _assert_device_exists(device_id, prometheus)
    try:
        k8s.restart_daemonset(
            namespace=settings.inference_namespace,
            name=settings.inference_daemonset,
        )
    except KubernetesUnavailable as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return InferenceRestartResponse(
        device_id=device_id,
        namespace=settings.inference_namespace,
        daemonset=settings.inference_daemonset,
        scope=ImageSetScope.FLEET_WIDE,
        note=(
            f"Inference DaemonSet {settings.inference_namespace}/"
            f"{settings.inference_daemonset} rollout-restarted. Today this rolls every "
            "Nano in the fleet (Spec 008 demo scope)."
        ),
    )


@router.post(
    "/devices/{device_id}/inference/rollback",
    response_model=InferenceRollbackResponse,
)
def rollback_inference(
    device_id: str,
    prometheus: PrometheusDep,
    k8s: K8sDep,
) -> InferenceRollbackResponse:
    """Roll the inference image back to the DaemonSet's immediately previous revision.

    First-class rollback: reads the cluster's ControllerRevision history to find the
    prior image, then re-patches the DaemonSet to it. v1 fleet-wide like set-image.

    Errors: 404 — ``device_id`` not in the fleet view; 502 — Prometheus (device check),
    no prior revision to roll back to, or the k8s read/PATCH failed.
    """
    _assert_device_exists(device_id, prometheus)
    try:
        image = k8s.previous_daemonset_image(
            namespace=settings.inference_namespace,
            name=settings.inference_daemonset,
            container=settings.inference_container,
        )
        k8s.patch_daemonset_image(
            namespace=settings.inference_namespace,
            name=settings.inference_daemonset,
            container=settings.inference_container,
            image=image,
        )
    except KubernetesUnavailable as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return InferenceRollbackResponse(
        device_id=device_id,
        image=image,
        namespace=settings.inference_namespace,
        daemonset=settings.inference_daemonset,
        scope=ImageSetScope.FLEET_WIDE,
        note=(
            f"Inference DaemonSet {settings.inference_namespace}/"
            f"{settings.inference_daemonset} rolled back to {image} (its previous "
            "revision). Today this rolls back every Nano in the fleet (Spec 008 demo scope)."
        ),
    )


@router.get("/models", response_model=list[ModelVersionView])
def list_models(catalog: CatalogDep) -> list[ModelVersionView]:
    """Available model versions from eai-catalog — the fleet UI's model selector source.

    Read live from the catalog (the fleet keeps no model state); ``id`` on each entry is
    the ``model_version_id`` the deploy route takes.

    Errors: 502 — the catalog query failed (unreachable / bad response).
    """
    try:
        return catalog.list_models()
    except CatalogUnavailable as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


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


@router.post(
    "/devices/{device_id}/recordings/pull",
    response_model=RecordingsPullResponse,
)
def pull_recordings(
    device_id: str,
    request: RecordingsPullRequest,
    prometheus: PrometheusDep,
) -> RecordingsPullResponse:
    """Pull one nano's saved recordings (mp4 + ndjson sidecar) into the shared dir.

    Central-initiated PULL (Spec 024): lists the nano's ``/api/sessions/saved`` and
    downloads any session not already on disk under
    ``recordings_dir/<device_id>/<inference_id>/``. The eai-catalog device-prediction
    ingest reads sidecars from there. ``nano_base_url`` + ``nano_token`` are
    caller-supplied (fleet keeps no device→URL map); a k8s CronJob or operator drives
    the schedule. Idempotent — present files are skipped.

    Errors: 404 if ``device_id`` isn't in the fleet view; 502 if Prometheus (used to
    validate the device) or the nano download fails.
    """
    _assert_device_exists(device_id, prometheus)
    dest = settings.recordings_dir / device_id
    puller = RecordingsPuller(
        base_url=request.nano_base_url,
        token=request.nano_token,
        dest_dir=dest,
        timeout_s=settings.recordings_pull_timeout_s,
        page_size=settings.recordings_pull_page_size,
    )
    try:
        summary = puller.reconcile()
    except httpx2.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return RecordingsPullResponse(device_id=device_id, dest_dir=str(dest), **summary.model_dump())

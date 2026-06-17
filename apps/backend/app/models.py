"""Fleet data models — strict Pydantic (extra='forbid', StrEnum).

The fleet view is **derived** (Spec 008), so these are read-only response shapes —
there is no DB table and no heartbeat payload anymore. A ``DeviceView`` is assembled
from Prometheus series (see ``prometheus.py``), not persisted.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class InferenceState(StrEnum):
    """Pipeline state for a nano (mirrors eai-nano).

    Note: there is no ``eai_inference_state`` Prometheus metric (state was a
    heartbeat field, now removed). Only RUNNING/STOPPED are *derived* today —
    from whether the device reports frames. The other members are kept for parity
    with eai-nano and for when inference exposes a state metric.
    """

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class FleetHealth(StrEnum):
    """Derived per-device health for the fleet view."""

    ONLINE = "online"
    OFFLINE = "offline"


class DeviceView(BaseModel):
    """One device in the fleet view, derived from Prometheus.

    Identity is the nano's ``device_id`` (the external label the node-local
    Prometheus agent stamps on remote_write, == the KubeEdge node name).
    """

    model_config = ConfigDict(extra="forbid")

    device_id: str
    name: str
    state: InferenceState
    fps: float = Field(ge=0.0)
    gpu_utilization: float = Field(ge=0.0)
    health: FleetHealth
    chromium_running: bool | None = None


class FleetView(BaseModel):
    """The whole fleet."""

    model_config = ConfigDict(extra="forbid")

    devices: list[DeviceView]
    total: int = Field(ge=0)
    online: int = Field(ge=0)


class InferenceImageRequest(BaseModel):
    """POST body for setting the inference image on a device."""

    model_config = ConfigDict(extra="forbid")

    image: str = Field(min_length=1, description="Full container image ref including tag.")


class ImageSetScope(StrEnum):
    """Effective blast radius of a single image-set call.

    v1 is always ``FLEET_WIDE`` because the inference workload is one DaemonSet
    across all Nanos. ``DEVICE`` is reserved for when per-Nano control lands
    (per-device Deployment or DaemonSet overlay).
    """

    FLEET_WIDE = "fleet-wide"
    DEVICE = "device"


class InferenceImageResponse(BaseModel):
    """Response from ``POST /api/fleet/devices/{id}/inference/image``."""

    model_config = ConfigDict(extra="forbid")

    device_id: str
    image: str
    scope: ImageSetScope
    note: str


class ModelDeployRequest(BaseModel):
    """POST body for deploying a catalog model package to one nano backend."""

    model_config = ConfigDict(extra="forbid")

    nano_base_url: str = Field(min_length=1, description="Reachable eai-nano backend base URL.")
    nano_token: str = Field(
        default="", description="Bearer token for the nano backend, if enabled."
    )


class ModelDeployResponse(BaseModel):
    """Response from ``POST /api/fleet/devices/{id}/models/{model_version_id}/deploy``."""

    model_config = ConfigDict(extra="forbid")

    device_id: str
    model_version_id: str
    model_id: str
    cached_package: str
    package_sha256: str
    nano_model_id: str
    scope: ImageSetScope


class RecordingsPullRequest(BaseModel):
    """POST body for pulling one nano's saved recordings into the shared dir.

    base_url + token are caller-supplied (fleet has no device→URL map; Spec 008),
    mirroring the model-deploy contract.
    """

    model_config = ConfigDict(extra="forbid")

    nano_base_url: str = Field(min_length=1, description="Reachable eai-nano backend base URL.")
    nano_token: str = Field(
        default="", description="Bearer token for the nano backend, if enabled."
    )


class RecordingsPullResponse(BaseModel):
    """Response from ``POST /api/fleet/devices/{id}/recordings/pull`` — the pull tally."""

    model_config = ConfigDict(extra="forbid")

    device_id: str
    dest_dir: str
    sessions_total: int
    pulled: int
    skipped: int
    failed: int
    bytes_pulled: int

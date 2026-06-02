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


class FleetView(BaseModel):
    """The whole fleet."""

    model_config = ConfigDict(extra="forbid")

    devices: list[DeviceView]
    total: int = Field(ge=0)
    online: int = Field(ge=0)


class HealthStatus(BaseModel):
    """Health check response."""

    model_config = ConfigDict(extra="forbid")

    status: str

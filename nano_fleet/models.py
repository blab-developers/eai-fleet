"""Fleet data models — strict SQLModel/Pydantic (extra='forbid', StrEnum)."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Timezone-aware UTC now (naive for SQLite compatibility)."""
    return datetime.now(UTC).replace(tzinfo=None)


class InferenceState(StrEnum):
    """Pipeline state reported by a nano (mirrors eai-nano)."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class FleetHealth(StrEnum):
    """Derived per-device health for the fleet view."""

    ONLINE = "online"
    OFFLINE = "offline"


# ---- DB table -------------------------------------------------------------


class Device(SQLModel, table=True):
    """A registered Jetson nano in the fleet (one row per device)."""

    model_config = ConfigDict(extra="forbid")  # type: ignore[assignment]

    device_id: str = Field(primary_key=True, min_length=1)
    name: str = Field(default="", max_length=128)
    location: str = Field(default="", max_length=128)
    state: InferenceState = Field(default=InferenceState.STOPPED)
    fps: float = Field(default=0.0, ge=0.0)
    uptime_s: int = Field(default=0, ge=0)
    last_error: str | None = Field(default=None)
    image_tag: str | None = Field(default=None)  # which container image is running
    last_seen: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)


# ---- API payloads ---------------------------------------------------------


class Heartbeat(SQLModel):
    """Telemetry a nano POSTs to the fleet manager (~every 10s)."""

    model_config = ConfigDict(extra="forbid")  # type: ignore[assignment]

    device_id: str = Field(min_length=1)
    name: str = ""
    location: str = ""
    state: InferenceState = InferenceState.STOPPED
    fps: float = Field(default=0.0, ge=0.0)
    uptime_s: int = Field(default=0, ge=0)
    last_error: str | None = None
    image_tag: str | None = None


class DeviceView(SQLModel):
    """One device in the fleet view (Device + derived health)."""

    model_config = ConfigDict(extra="forbid")  # type: ignore[assignment]

    device_id: str
    name: str
    location: str
    state: InferenceState
    fps: float
    uptime_s: int
    last_error: str | None
    image_tag: str | None
    last_seen: datetime
    health: FleetHealth


class FleetView(SQLModel):
    """The whole fleet."""

    model_config = ConfigDict(extra="forbid")  # type: ignore[assignment]

    devices: list[DeviceView]
    total: int = Field(ge=0)
    online: int = Field(ge=0)


class HealthStatus(SQLModel):
    """Health check response."""

    model_config = ConfigDict(extra="forbid")  # type: ignore[assignment]

    status: str

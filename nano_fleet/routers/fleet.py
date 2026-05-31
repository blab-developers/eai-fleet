"""Fleet endpoints: heartbeat ingest + fleet view.

Nanos POST a heartbeat (~every 10s); the fleet view derives online/offline from
heartbeat age. Identity/liveness can also be cross-checked against KubeEdge k8s
Node status on the server (Spec 008) — this service is the app-level registry.
"""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models import (
    Device,
    DeviceView,
    FleetHealth,
    FleetView,
    Heartbeat,
    utc_now,
)

router = APIRouter(prefix="/api/fleet", tags=["fleet"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.post("/heartbeat", response_model=DeviceView)
def ingest_heartbeat(hb: Heartbeat, session: SessionDep) -> DeviceView:
    """Upsert a device from its heartbeat and stamp last_seen."""
    device = session.get(Device, hb.device_id)
    now = utc_now()
    if device is None:
        device = Device(device_id=hb.device_id, created_at=now)
    device.name = hb.name or device.name
    device.location = hb.location or device.location
    device.state = hb.state
    device.fps = hb.fps
    device.uptime_s = hb.uptime_s
    device.last_error = hb.last_error
    device.image_tag = hb.image_tag
    device.last_seen = now
    session.add(device)
    session.commit()
    session.refresh(device)
    return _to_view(device, now)


@router.get("/devices", response_model=FleetView)
def list_devices(session: SessionDep) -> FleetView:
    """The whole fleet with derived online/offline health."""
    now = utc_now()
    devices = session.exec(select(Device)).all()
    views = [_to_view(d, now) for d in devices]
    online = sum(1 for v in views if v.health == FleetHealth.ONLINE)
    return FleetView(devices=views, total=len(views), online=online)


def _to_view(device: Device, now: datetime) -> DeviceView:
    """Derive online/offline from heartbeat staleness."""
    offline = now - device.last_seen > timedelta(seconds=settings.offline_after_s)
    return DeviceView(
        device_id=device.device_id,
        name=device.name,
        location=device.location,
        state=device.state,
        fps=device.fps,
        uptime_s=device.uptime_s,
        last_error=device.last_error,
        image_tag=device.image_tag,
        last_seen=device.last_seen,
        health=FleetHealth.OFFLINE if offline else FleetHealth.ONLINE,
    )

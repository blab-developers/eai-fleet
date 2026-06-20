"""Demo fleet data for explicit local/dev runs.

fleet-mgr is stateless: these devices are never persisted and only appear when
``EAI_FLEET_DEMO_MODE=true``. The frontend can hide them via its per-browser demo
preference because every sample row carries ``demo=True``.
"""

from app.models import DeviceView, FleetHealth, FleetView, InferenceState

DEMO_DEVICE_IDS = {"demo-nano-00", "demo-nano-01", "demo-nano-02"}

_DEMO_DEVICES = [
    DeviceView(
        device_id="demo-nano-00",
        name="OR-1 Demo Nano",
        state=InferenceState.RUNNING,
        fps=29.5,
        gpu_utilization=73.0,
        health=FleetHealth.ONLINE,
        chromium_running=True,
        demo=True,
    ),
    DeviceView(
        device_id="demo-nano-01",
        name="OR-2 Demo Nano",
        state=InferenceState.STOPPED,
        fps=0.0,
        gpu_utilization=8.0,
        health=FleetHealth.ONLINE,
        chromium_running=False,
        demo=True,
    ),
    DeviceView(
        device_id="demo-nano-02",
        name="Lab Demo Nano",
        state=InferenceState.STOPPED,
        fps=0.0,
        gpu_utilization=0.0,
        health=FleetHealth.OFFLINE,
        chromium_running=None,
        demo=True,
    ),
]


def demo_fleet_view() -> FleetView:
    """Return a fresh canned FleetView for local demos and dev integration tests."""
    devices = [device.model_copy(deep=True) for device in _DEMO_DEVICES]
    online = sum(1 for device in devices if device.health == FleetHealth.ONLINE)
    return FleetView(devices=devices, total=len(devices), online=online)


def with_demo_when_empty(view: FleetView, demo_mode: bool) -> FleetView:
    """Use demo data only when explicitly enabled and the real derived view is empty."""
    if demo_mode and view.total == 0:
        return demo_fleet_view()
    return view

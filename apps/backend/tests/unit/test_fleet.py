"""Fleet manager: the view is DERIVED from KubeEdge node status + Prometheus.

No heartbeat ingest exists anymore (Spec 008). These tests drive the API with a fake
Prometheus and assert online/offline (from node Ready) and telemetry (from
``eai_inference_*``) compose into the fleet view correctly.
"""

from typing import Any

from fastapi.testclient import TestClient

from app.prometheus import FPS_METRIC, GPU_METRIC, build_fleet_view
from tests.conftest import FakePrometheus


def test_health(client: TestClient) -> None:
    """Health endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_heartbeat_endpoint_is_gone(client: TestClient) -> None:
    """The retired heartbeat ingest must not exist (Spec 008)."""
    response = client.post("/api/fleet/heartbeat", json={"device_id": "jetson-01"})
    assert response.status_code == 404


def test_ready_node_with_frames_is_online_and_running(
    client: TestClient, fake_prom: FakePrometheus
) -> None:
    """A Ready nano reporting frames shows ONLINE + RUNNING with its telemetry."""
    fake_prom.ready = {"jetson-01": 1.0}
    fake_prom.gauges = {FPS_METRIC: {"jetson-01": 29.5}, GPU_METRIC: {"jetson-01": 73.0}}

    response = client.get("/api/fleet/devices")
    assert response.status_code == 200
    view: dict[str, Any] = response.json()
    assert view["total"] == 1
    assert view["online"] == 1
    device = view["devices"][0]
    assert device["device_id"] == "jetson-01"
    assert device["health"] == "online"
    assert device["state"] == "running"
    assert device["fps"] == 29.5
    assert device["gpu_utilization"] == 73.0


def test_ready_node_without_frames_is_online_but_stopped(
    client: TestClient, fake_prom: FakePrometheus
) -> None:
    """A Ready nano with no frames is ONLINE but STOPPED (idle ≠ offline)."""
    fake_prom.ready = {"jetson-01": 1.0}

    view = client.get("/api/fleet/devices").json()
    device = view["devices"][0]
    assert device["health"] == "online"
    assert device["state"] == "stopped"
    assert device["fps"] == 0.0


def test_not_ready_node_is_offline_even_with_stale_metrics(
    client: TestClient, fake_prom: FakePrometheus
) -> None:
    """A node that dropped its CloudCore link is OFFLINE even if metrics linger."""
    fake_prom.ready = {}  # KSM no longer reports it Ready
    fake_prom.gauges = {FPS_METRIC: {"jetson-01": 29.5}}  # stale remote_write residue

    view = client.get("/api/fleet/devices").json()
    device = view["devices"][0]
    assert device["health"] == "offline"
    assert view["online"] == 0


def test_fleet_view_counts_mixed_health(client: TestClient, fake_prom: FakePrometheus) -> None:
    """Totals and online count are correct across a mixed fleet."""
    fake_prom.ready = {"jetson-00": 1.0, "jetson-01": 1.0, "jetson-02": 0.0}
    fake_prom.gauges = {FPS_METRIC: {"jetson-00": 30.0, "jetson-01": 12.0}}

    view = client.get("/api/fleet/devices").json()
    assert view["total"] == 3
    assert view["online"] == 2
    by_id = {d["device_id"]: d for d in view["devices"]}
    assert by_id["jetson-02"]["health"] == "offline"


def test_prometheus_down_returns_502(client: TestClient, fake_prom: FakePrometheus) -> None:
    """If central Prometheus can't be queried, the derived view is unavailable."""
    fake_prom.fail = True
    response = client.get("/api/fleet/devices")
    assert response.status_code == 502


def test_build_fleet_view_unions_node_and_metric_identities() -> None:
    """A device seen only in metrics (not yet in node Ready) still appears."""
    prom = FakePrometheus()
    prom.ready = {"jetson-00": 1.0}
    prom.gauges = {FPS_METRIC: {"jetson-01": 5.0}}

    view = build_fleet_view(prom)  # type: ignore[arg-type]  # FakePrometheus duck-types the client
    ids = {d.device_id for d in view.devices}
    assert ids == {"jetson-00", "jetson-01"}

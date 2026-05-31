"""Fleet manager: heartbeat ingest, upsert, derived online/offline."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ... import models


def test_health(client: TestClient) -> None:
    """Health endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_heartbeat_registers_device(client: TestClient) -> None:
    """Heartbeat creates a new device."""
    response = client.post(
        "/api/fleet/heartbeat",
        json={"device_id": "jetson-01", "name": "OR-1", "state": "running", "fps": 29.5},
    )
    assert response.status_code == 200
    device: dict[str, Any] = response.json()
    assert device["device_id"] == "jetson-01"
    assert device["name"] == "OR-1"
    assert device["state"] == "running"
    assert device["fps"] == 29.5
    assert device["health"] == "online"


def test_heartbeat_upserts(client: TestClient) -> None:
    """Heartbeat updates existing device instead of duplicating."""
    client.post("/api/fleet/heartbeat", json={"device_id": "jetson-01", "fps": 10.0})
    client.post(
        "/api/fleet/heartbeat",
        json={"device_id": "jetson-01", "fps": 30.0, "state": "running"},
    )
    response = client.get("/api/fleet/devices")
    view: dict[str, Any] = response.json()
    assert view["total"] == 1
    assert view["devices"][0]["fps"] == 30.0


def test_fleet_view_totals_and_health(client: TestClient) -> None:
    """Fleet view correctly counts devices and health."""
    for i in range(3):
        client.post(
            "/api/fleet/heartbeat",
            json={"device_id": f"jetson-0{i}", "state": "running"},
        )
    response = client.get("/api/fleet/devices")
    view: dict[str, Any] = response.json()
    assert view["total"] == 3
    assert view["online"] == 3
    assert all(device["health"] == "online" for device in view["devices"])


def test_offline_when_stale(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Device marked offline when heartbeat becomes stale."""
    client.post("/api/fleet/heartbeat", json={"device_id": "jetson-01"})
    now = models.utc_now()
    monkeypatch.setattr(
        "nano_fleet.routers.fleet.utc_now",
        lambda: now + timedelta(seconds=120),
    )
    response = client.get("/api/fleet/devices")
    view: dict[str, Any] = response.json()
    assert view["online"] == 0
    assert view["devices"][0]["health"] == "offline"


def test_strict_payload_rejects_unknown_fields(client: TestClient) -> None:
    """Pydantic strict mode (extra='forbid') rejects unknown fields."""
    response = client.post("/api/fleet/heartbeat", json={"device_id": "x", "bogus": 1})
    assert response.status_code == 422


def test_heartbeat_preserves_existing_fields(client: TestClient) -> None:
    """Empty heartbeat fields don't overwrite existing values."""
    client.post(
        "/api/fleet/heartbeat",
        json={"device_id": "jetson-01", "name": "Original", "location": "Building A"},
    )
    client.post("/api/fleet/heartbeat", json={"device_id": "jetson-01"})
    response = client.get("/api/fleet/devices")
    view: dict[str, Any] = response.json()
    device = view["devices"][0]
    assert device["name"] == "Original"
    assert device["location"] == "Building A"

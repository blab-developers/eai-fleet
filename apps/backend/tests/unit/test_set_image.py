"""Image-set endpoint — patches the inference DaemonSet, validates against fleet view.

The endpoint is fleet-wide-under-a-per-device-shape (v1; see route docstring), so the
tests exercise the device-validation path (404 for unknown device, 200 for a known
device) and the k8s-PATCH wiring (FakeK8s records what the route would have sent).
"""

from fastapi.testclient import TestClient

from app.k8s import KubernetesUnavailable
from app.prometheus import FPS_METRIC
from tests.conftest import FakeK8s, FakePrometheus


def test_set_image_on_known_device_patches_daemonset(
    client: TestClient,
    fake_prom: FakePrometheus,
    fake_k8s: FakeK8s,
) -> None:
    """A device that's in the fleet view → 200 + one PATCH recorded against the DS."""
    fake_prom.ready = {"jetson-01": 1.0}
    fake_prom.gauges = {FPS_METRIC: {"jetson-01": 29.5}}

    response = client.post(
        "/api/fleet/devices/jetson-01/inference/image",
        json={"image": "registry.endoscopeai.com/eai-nano/inference:v0.4.2"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["device_id"] == "jetson-01"
    assert body["image"] == "registry.endoscopeai.com/eai-nano/inference:v0.4.2"
    assert body["scope"] == "fleet-wide"
    assert "DaemonSet" in body["note"]

    assert fake_k8s.patches == [
        (
            "eai-nano",
            "eai-nano-inference",
            "inference",
            "registry.endoscopeai.com/eai-nano/inference:v0.4.2",
        )
    ]


def test_set_image_on_unknown_device_404s_and_does_not_patch(
    client: TestClient,
    fake_prom: FakePrometheus,
    fake_k8s: FakeK8s,
) -> None:
    """Unknown device_id is rejected BEFORE the k8s PATCH fires (typo guard)."""
    fake_prom.ready = {"jetson-01": 1.0}

    response = client.post(
        "/api/fleet/devices/typo-nano/inference/image",
        json={"image": "registry.endoscopeai.com/eai-nano/inference:v0.4.2"},
    )

    assert response.status_code == 404
    assert "typo-nano" in response.json()["detail"]
    assert fake_k8s.patches == []


def test_set_image_when_k8s_unavailable_returns_502(
    client: TestClient,
    fake_prom: FakePrometheus,
    fake_k8s: FakeK8s,
) -> None:
    """A failed k8s PATCH surfaces as 502 — the client sees a clean upstream error."""
    fake_prom.ready = {"jetson-01": 1.0}
    fake_k8s.fail = KubernetesUnavailable("apiserver down")

    response = client.post(
        "/api/fleet/devices/jetson-01/inference/image",
        json={"image": "registry.endoscopeai.com/eai-nano/inference:v0.4.2"},
    )

    assert response.status_code == 502
    assert "apiserver down" in response.json()["detail"]


def test_set_image_rejects_empty_image(client: TestClient, fake_prom: FakePrometheus) -> None:
    """Pydantic validation — an empty image string is 422 before we hit the route body."""
    fake_prom.ready = {"jetson-01": 1.0}

    response = client.post(
        "/api/fleet/devices/jetson-01/inference/image",
        json={"image": ""},
    )

    assert response.status_code == 422


def test_set_image_rejects_unknown_field(client: TestClient, fake_prom: FakePrometheus) -> None:
    """extra='forbid' on the request — unknown JSON fields fail validation."""
    fake_prom.ready = {"jetson-01": 1.0}

    response = client.post(
        "/api/fleet/devices/jetson-01/inference/image",
        json={"image": "x:y", "rollback": True},
    )

    assert response.status_code == 422

"""Running-version read + restart + first-class rollback (task: Fleet Manager UI gaps).

These three endpoints round out the fleet's device operations:

  * ``GET /inference/image`` — the running version, read live from k8s (the read the
    mutating client used to lack). It is a SEPARATE endpoint from the derived
    ``GET /devices`` so that path stays k8s-free.
  * ``POST /devices/{id}/inference/restart`` — ``kubectl rollout restart`` on the DS.
  * ``POST /devices/{id}/inference/rollback`` — re-patch to the DaemonSet's previous
    revision image; turns the old implicit "re-deploy the prior tag" into a real verb.

All three are fleet-wide-under-a-per-device-shape (v1), so the mutating pair validate
``device_id`` against the fleet view before touching k8s (typo guard), exactly like
set-image.
"""

from fastapi.testclient import TestClient

from app.k8s import KubernetesUnavailable
from app.prometheus import FPS_METRIC
from tests.conftest import FakeK8s, FakePrometheus

_NS = "eai-nano"
_DS = "eai-nano-inference"
_CONTAINER = "inference"


# --- GET /inference/image (running version) --------------------------------------------


def test_get_inference_image_returns_current(
    client: TestClient, fake_prom: FakePrometheus, fake_k8s: FakeK8s
) -> None:
    fake_k8s.current_image = "registry.endoscopeai.com/eai-nano/inference:v3.1.0"

    response = client.get("/api/fleet/inference/image")

    assert response.status_code == 200
    body = response.json()
    assert body["image"] == "registry.endoscopeai.com/eai-nano/inference:v3.1.0"
    assert body["namespace"] == _NS
    assert body["daemonset"] == _DS
    assert body["container"] == _CONTAINER
    assert body["scope"] == "fleet-wide"


def test_get_inference_image_502_when_k8s_unavailable(
    client: TestClient, fake_prom: FakePrometheus, fake_k8s: FakeK8s
) -> None:
    fake_k8s.fail = KubernetesUnavailable("apiserver down")

    response = client.get("/api/fleet/inference/image")

    assert response.status_code == 502
    assert "apiserver down" in response.json()["detail"]


# --- POST /devices/{id}/inference/restart ----------------------------------------------


def test_restart_known_device_rolls_daemonset(
    client: TestClient, fake_prom: FakePrometheus, fake_k8s: FakeK8s
) -> None:
    fake_prom.ready = {"jetson-01": 1.0}
    fake_prom.gauges = {FPS_METRIC: {"jetson-01": 29.5}}

    response = client.post("/api/fleet/devices/jetson-01/inference/restart")

    assert response.status_code == 200
    body = response.json()
    assert body["device_id"] == "jetson-01"
    assert body["scope"] == "fleet-wide"
    assert "restart" in body["note"].lower()
    assert fake_k8s.restarts == [(_NS, _DS)]


def test_restart_unknown_device_404s_and_does_not_restart(
    client: TestClient, fake_prom: FakePrometheus, fake_k8s: FakeK8s
) -> None:
    fake_prom.ready = {"jetson-01": 1.0}

    response = client.post("/api/fleet/devices/typo-nano/inference/restart")

    assert response.status_code == 404
    assert "typo-nano" in response.json()["detail"]
    assert fake_k8s.restarts == []


def test_restart_502_when_k8s_unavailable(
    client: TestClient, fake_prom: FakePrometheus, fake_k8s: FakeK8s
) -> None:
    fake_prom.ready = {"jetson-01": 1.0}
    fake_k8s.fail = KubernetesUnavailable("patch rejected")

    response = client.post("/api/fleet/devices/jetson-01/inference/restart")

    assert response.status_code == 502
    assert "patch rejected" in response.json()["detail"]


# --- POST /devices/{id}/inference/rollback ---------------------------------------------


def test_rollback_repatches_to_previous_revision_image(
    client: TestClient, fake_prom: FakePrometheus, fake_k8s: FakeK8s
) -> None:
    fake_prom.ready = {"jetson-01": 1.0}
    fake_k8s.previous_image = "registry.endoscopeai.com/eai-nano/inference:v1"

    response = client.post("/api/fleet/devices/jetson-01/inference/rollback")

    assert response.status_code == 200
    body = response.json()
    assert body["image"] == "registry.endoscopeai.com/eai-nano/inference:v1"
    assert body["device_id"] == "jetson-01"
    assert body["scope"] == "fleet-wide"
    # The rollback IS a re-patch to the previous image.
    assert fake_k8s.patches == [
        (_NS, _DS, _CONTAINER, "registry.endoscopeai.com/eai-nano/inference:v1")
    ]


def test_rollback_unknown_device_404s_and_does_not_patch(
    client: TestClient, fake_prom: FakePrometheus, fake_k8s: FakeK8s
) -> None:
    fake_prom.ready = {"jetson-01": 1.0}

    response = client.post("/api/fleet/devices/typo-nano/inference/rollback")

    assert response.status_code == 404
    assert fake_k8s.patches == []


def test_rollback_502_when_no_prior_revision(
    client: TestClient, fake_prom: FakePrometheus, fake_k8s: FakeK8s
) -> None:
    fake_prom.ready = {"jetson-01": 1.0}
    fake_k8s.previous_image = None  # no revision to roll back to

    response = client.post("/api/fleet/devices/jetson-01/inference/rollback")

    assert response.status_code == 502
    assert "roll back" in response.json()["detail"]
    assert fake_k8s.patches == []  # nothing applied when there's no target

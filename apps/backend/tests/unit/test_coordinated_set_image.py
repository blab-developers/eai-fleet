"""Coordinated shutdown on image change (task: coordinate shutdown).

When set-image is given a ``nano_base_url``, the fleet must ask that nano to drain
(finalize any in-progress recording, stop the pipeline) and REQUIRE its confirmation
BEFORE patching the image — so an image swap never drops a recording. These tests pin:

  * the ORDER (drain happens before the k8s patch),
  * the SAFETY (a failed / unconfirmed drain leaves the image UNCHANGED — no patch),
  * back-compat (no ``nano_base_url`` → immediate patch, uncoordinated).

The nano call is faked by monkeypatching ``fleet.NanoClient`` (same pattern the model-deploy
tests use for ``ModelDeployer``).
"""

import pytest
from fastapi.testclient import TestClient

import app.routers.fleet as fleet_mod
from app.nano import NanoUnavailable, ShutdownAck
from tests.conftest import FakeK8s, FakePrometheus

_DEVICE = "jetson-01"
_IMAGE = "registry.endoscopeai.com/eai-nano/inference:v2"
_NANO_URL = "http://nano-01:8000"


class _FakeNano:
    """Records the drain call; configurable ack / failure. Shared across a test via class attrs."""

    calls: list[tuple[str, str]] = []
    ack: ShutdownAck | None = None
    fail: Exception | None = None

    def __init__(self, base_url, token="", timeout_s=30.0):
        self._base_url = base_url
        self._token = token

    def prepare_shutdown(self) -> ShutdownAck:
        _FakeNano.calls.append((self._base_url, self._token))
        if _FakeNano.fail is not None:
            raise _FakeNano.fail
        assert _FakeNano.ack is not None
        return _FakeNano.ack


@pytest.fixture(autouse=True)
def _patch_nano(monkeypatch: pytest.MonkeyPatch):
    _FakeNano.calls = []
    _FakeNano.ack = ShutdownAck(drained=True, recordings_finalized=1, pipeline_stopped=True)
    _FakeNano.fail = None
    monkeypatch.setattr(fleet_mod, "NanoClient", _FakeNano)


def _set_image(client: TestClient, body: dict):
    return client.post(f"/api/fleet/devices/{_DEVICE}/inference/image", json=body)


def test_coordinated_drains_then_patches(
    client: TestClient, fake_prom: FakePrometheus, fake_k8s: FakeK8s
) -> None:
    fake_prom.ready = {_DEVICE: 1.0}
    _FakeNano.ack = ShutdownAck(drained=True, recordings_finalized=2, pipeline_stopped=True)

    resp = _set_image(client, {"image": _IMAGE, "nano_base_url": _NANO_URL, "nano_token": "t"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["coordinated"] is True
    assert body["recordings_finalized"] == 2
    # The drain was called with the supplied URL/token, and the patch DID happen.
    assert _FakeNano.calls == [(_NANO_URL, "t")]
    assert fake_k8s.patches == [
        ("eai-nano", "eai-nano-inference", "inference", _IMAGE),
    ]


def test_failed_drain_leaves_image_unchanged(
    client: TestClient, fake_prom: FakePrometheus, fake_k8s: FakeK8s
) -> None:
    fake_prom.ready = {_DEVICE: 1.0}
    _FakeNano.fail = NanoUnavailable("connection refused")

    resp = _set_image(client, {"image": _IMAGE, "nano_base_url": _NANO_URL})

    assert resp.status_code == 502
    assert "NOT changed" in resp.json()["detail"]
    assert _FakeNano.calls == [(_NANO_URL, "")]  # drain was attempted
    assert fake_k8s.patches == []  # ...but the image was NOT patched


def test_nano_reports_not_drained_blocks_patch(
    client: TestClient, fake_prom: FakePrometheus, fake_k8s: FakeK8s
) -> None:
    fake_prom.ready = {_DEVICE: 1.0}
    _FakeNano.ack = ShutdownAck(drained=False)

    resp = _set_image(client, {"image": _IMAGE, "nano_base_url": _NANO_URL})

    assert resp.status_code == 502
    assert "did not confirm" in resp.json()["detail"]
    assert fake_k8s.patches == []  # not drained → no patch


def test_no_nano_url_patches_immediately_uncoordinated(
    client: TestClient, fake_prom: FakePrometheus, fake_k8s: FakeK8s
) -> None:
    fake_prom.ready = {_DEVICE: 1.0}

    resp = _set_image(client, {"image": _IMAGE})

    assert resp.status_code == 200
    body = resp.json()
    assert body["coordinated"] is False
    assert body["recordings_finalized"] is None
    assert _FakeNano.calls == []  # no drain attempted
    assert fake_k8s.patches == [("eai-nano", "eai-nano-inference", "inference", _IMAGE)]

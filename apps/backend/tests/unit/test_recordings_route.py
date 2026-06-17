"""POST /api/fleet/devices/{id}/recordings/pull — route-level tests.

Core pull logic is covered in test_recordings_pull.py; here we exercise the route
wiring: the Prometheus device gate (404), the happy-path summary shape, and the 502
mapping when the nano download fails. RecordingsPuller is replaced with a fake.
"""

import httpx2
import pytest

import app.routers.fleet as fleet_mod
from recordings_pull import PullSummary

_DEVICE = "orin-01"


class _FakePuller:
    """Replaces RecordingsPuller in the route — records init, returns a canned summary."""

    last_init: dict = {}
    raise_on_reconcile: Exception | None = None

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        dest_dir: object,
        timeout_s: float = 30.0,
        page_size: int = 100,
    ) -> None:
        _FakePuller.last_init = {"base_url": base_url, "token": token, "dest_dir": str(dest_dir)}

    def reconcile(self) -> PullSummary:
        if _FakePuller.raise_on_reconcile is not None:
            raise _FakePuller.raise_on_reconcile
        return PullSummary(sessions_total=2, pulled=3, skipped=1, failed=0, bytes_pulled=123)


@pytest.fixture(autouse=True)
def _reset() -> None:
    _FakePuller.last_init = {}
    _FakePuller.raise_on_reconcile = None


@pytest.fixture
def patched_puller(monkeypatch) -> None:
    monkeypatch.setattr(fleet_mod, "RecordingsPuller", _FakePuller)


def test_pull_happy_path(client, fake_prom, patched_puller) -> None:
    fake_prom.ready = {_DEVICE: 1.0}  # device present in the fleet view
    resp = client.post(
        f"/api/fleet/devices/{_DEVICE}/recordings/pull",
        json={"nano_base_url": "http://nano:8000", "nano_token": "tok"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["device_id"] == _DEVICE
    assert (body["sessions_total"], body["pulled"], body["skipped"]) == (2, 3, 1)
    assert body["dest_dir"].endswith(_DEVICE)
    assert _FakePuller.last_init["base_url"] == "http://nano:8000"
    assert _FakePuller.last_init["token"] == "tok"


def test_pull_unknown_device_404(client, fake_prom, patched_puller) -> None:
    fake_prom.ready = {}  # device not in fleet
    resp = client.post(
        f"/api/fleet/devices/{_DEVICE}/recordings/pull",
        json={"nano_base_url": "http://nano:8000"},
    )
    assert resp.status_code == 404, resp.text


def test_pull_nano_error_maps_to_502(client, fake_prom, patched_puller) -> None:
    fake_prom.ready = {_DEVICE: 1.0}
    _FakePuller.raise_on_reconcile = httpx2.HTTPError("nano down")
    resp = client.post(
        f"/api/fleet/devices/{_DEVICE}/recordings/pull",
        json={"nano_base_url": "http://nano:8000"},
    )
    assert resp.status_code == 502, resp.text

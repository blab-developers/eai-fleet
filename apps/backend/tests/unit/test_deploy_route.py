"""POST /api/fleet/devices/{id}/models/{mv}/deploy — route-level tests.

The HTTP fetch/push internals are covered in test_model_deploy_http.py; here we
exercise the route wiring: the Prometheus device gate (404), the happy-path
response shape, and the 502 mapping when the deployer fails. ``ModelDeployer`` is
replaced with a fake so no catalog or nano is contacted.
"""

from pathlib import Path

import httpx2
import pytest

import app.routers.fleet as fleet_mod
from app.model_deploy import (
    CachedModelPackage,
    ModelPackageManifest,
    NanoModelInstall,
)

_DEVICE = "orin-01"
_MV = "mv_123"


def _manifest() -> ModelPackageManifest:
    return ModelPackageManifest(
        model_version_id=_MV,
        model_id=_MV,
        name="YOLOv12 MT",
        weights_hash="c" * 64,
        artifact_filename="yolo12-mt.onnx",
        shards=[],
    )


class _FakeDeployer:
    """Replaces ModelDeployer in the route — records calls, returns canned data."""

    last_init: dict = {}
    pushed: dict = {}
    raise_on_cache: Exception | None = None

    def __init__(self, *, catalog_url, cache_dir, catalog_token="", timeout_s=60.0):
        _FakeDeployer.last_init = {
            "catalog_url": catalog_url,
            "cache_dir": cache_dir,
            "catalog_token": catalog_token,
            "timeout_s": timeout_s,
        }

    def cache_package(self, model_version_id: str) -> CachedModelPackage:
        if _FakeDeployer.raise_on_cache is not None:
            raise _FakeDeployer.raise_on_cache
        return CachedModelPackage(
            path=Path("/cache/models") / model_version_id / "package.zip",
            sha256="d" * 64,
            manifest=_manifest(),
        )

    def push_to_nano(self, cached, nano_base_url, nano_token=""):
        _FakeDeployer.pushed = {"url": nano_base_url, "token": nano_token}
        return NanoModelInstall(
            model_id=cached.manifest.model_id,
            weights_hash=cached.manifest.weights_hash,
            artifact_filename=cached.manifest.artifact_filename,
        )


@pytest.fixture(autouse=True)
def _reset_fake() -> None:
    _FakeDeployer.last_init = {}
    _FakeDeployer.pushed = {}
    _FakeDeployer.raise_on_cache = None


@pytest.fixture
def patched_deployer(monkeypatch) -> None:
    monkeypatch.setattr(fleet_mod, "ModelDeployer", _FakeDeployer)


def test_deploy_happy_path(client, fake_prom, patched_deployer) -> None:
    fake_prom.ready = {_DEVICE: 1.0}  # device present in the fleet view

    resp = client.post(
        f"/api/fleet/devices/{_DEVICE}/models/{_MV}/deploy",
        json={"nano_base_url": "http://nano:8500", "nano_token": "tok"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["device_id"] == _DEVICE
    assert body["model_version_id"] == _MV
    assert body["model_id"] == _MV
    assert body["nano_model_id"] == _MV
    assert body["package_sha256"] == "d" * 64
    assert body["cached_package"].endswith(f"{_MV}/package.zip")
    assert body["scope"] == "device"
    # The nano target from the request body reached push_to_nano.
    assert _FakeDeployer.pushed == {"url": "http://nano:8500", "token": "tok"}


def test_deploy_unknown_device_is_404(client, fake_prom, patched_deployer) -> None:
    fake_prom.ready = {}  # empty fleet → device not found

    resp = client.post(
        f"/api/fleet/devices/{_DEVICE}/models/{_MV}/deploy",
        json={"nano_base_url": "http://nano:8500"},
    )

    assert resp.status_code == 404
    assert _DEVICE in resp.json()["detail"]
    assert _FakeDeployer.last_init == {}  # never built the deployer


def test_deploy_maps_deployer_failure_to_502(client, fake_prom, patched_deployer) -> None:
    fake_prom.ready = {_DEVICE: 1.0}
    _FakeDeployer.raise_on_cache = httpx2.HTTPError("catalog 404")

    resp = client.post(
        f"/api/fleet/devices/{_DEVICE}/models/{_MV}/deploy",
        json={"nano_base_url": "http://nano:8500"},
    )

    assert resp.status_code == 502
    assert "catalog 404" in resp.json()["detail"]


def test_deploy_builds_deployer_from_settings(client, fake_prom, patched_deployer) -> None:
    from app.config import settings

    fake_prom.ready = {_DEVICE: 1.0}
    client.post(
        f"/api/fleet/devices/{_DEVICE}/models/{_MV}/deploy",
        json={"nano_base_url": "http://nano:8500"},
    )
    assert _FakeDeployer.last_init["catalog_url"] == settings.catalog_url
    assert _FakeDeployer.last_init["cache_dir"] == settings.model_cache_dir

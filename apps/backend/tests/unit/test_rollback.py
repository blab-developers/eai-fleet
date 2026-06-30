"""Update rollback + failed-update resilience (task: update rollback).

Fleet has no dedicated "rollback" verb — a stateless manager rolls back by re-deploying
the previous version. These tests model a **stateful nano** (it remembers the model_id it
last installed) and drive it through fleet's real deploy path to assert two properties:

  * **rollback** — re-deploying a prior ``model_version_id`` returns the nano to that
    version (v1 → v2 → v1), at both the route level and through the deployer's real
    multipart-push code against an in-process nano that installs whatever it's handed;
  * **failed / interrupted update keeps the last good version** — a deploy that fails
    (bad download, nano refuses mid-push, k8s patch error) is a 502 *and* leaves the nano
    on the version it was already running. Nothing half-applies.

The same property is checked for the inference-image deploy path (k8s DaemonSet patch).
"""

import io
import json
import zipfile
from pathlib import Path

import httpx2
import pytest

import app.routers.fleet as fleet_mod
from app import model_deploy
from app.model_deploy import (
    CachedModelPackage,
    ModelDeployer,
    ModelPackageManifest,
    NanoModelInstall,
)

_DEVICE = "orin-01"


# --- a stateful nano shared by the route-level tests -----------------------------------

class _Nano:
    """Remembers the model_id it last installed (its 'running version')."""

    active: str | None = None
    history: list[str] = []

    @classmethod
    def reset(cls) -> None:
        cls.active = None
        cls.history = []


class _StatefulDeployer:
    """Patches ModelDeployer in the route: push installs onto the shared _Nano.

    ``fail_cache`` / ``fail_push`` let a test simulate a broken download or a nano that
    refuses the upload — the deploy must then NOT change _Nano.active.
    """

    fail_cache: Exception | None = None
    fail_push: Exception | None = None

    def __init__(self, *, catalog_url, cache_dir, catalog_token="", timeout_s=60.0):
        self._cache_dir = Path(cache_dir)

    def cache_package(self, model_version_id: str) -> CachedModelPackage:
        if _StatefulDeployer.fail_cache is not None:
            raise _StatefulDeployer.fail_cache
        manifest = ModelPackageManifest(
            model_version_id=model_version_id,
            model_id=model_version_id,
            name="YOLOv12 MT",
            weights_hash="c" * 64,
            artifact_filename="model.onnx",
            shards=[],
        )
        return CachedModelPackage(
            path=self._cache_dir / model_version_id / "package.zip",
            sha256="d" * 64,
            manifest=manifest,
        )

    def push_to_nano(self, cached, nano_base_url, nano_token="") -> NanoModelInstall:
        if _StatefulDeployer.fail_push is not None:
            raise _StatefulDeployer.fail_push
        _Nano.active = cached.manifest.model_id  # the install takes effect here
        _Nano.history.append(cached.manifest.model_id)
        return NanoModelInstall(
            model_id=cached.manifest.model_id,
            weights_hash=cached.manifest.weights_hash,
            artifact_filename=cached.manifest.artifact_filename,
        )


@pytest.fixture(autouse=True)
def _patch_deployer(monkeypatch):
    _Nano.reset()
    _StatefulDeployer.fail_cache = None
    _StatefulDeployer.fail_push = None
    monkeypatch.setattr(fleet_mod, "ModelDeployer", _StatefulDeployer)


def _deploy(client, mv: str):
    return client.post(
        f"/api/fleet/devices/{_DEVICE}/models/{mv}/deploy",
        json={"nano_base_url": "http://nano:8000", "nano_token": ""},
    )


# --- rollback = re-deploy a prior version ----------------------------------------------

def test_redeploy_prior_version_rolls_back(client, fake_prom) -> None:
    fake_prom.ready = {_DEVICE: 1.0}

    assert _deploy(client, "mv_v1").status_code == 200
    assert _Nano.active == "mv_v1"

    assert _deploy(client, "mv_v2").status_code == 200
    assert _Nano.active == "mv_v2"

    # Roll back by deploying the earlier version again.
    resp = _deploy(client, "mv_v1")
    assert resp.status_code == 200
    assert resp.json()["nano_model_id"] == "mv_v1"
    assert _Nano.active == "mv_v1"
    assert _Nano.history == ["mv_v1", "mv_v2", "mv_v1"]


# --- a failed/interrupted update keeps the last good version ----------------------------

def test_failed_download_keeps_last_good_version(client, fake_prom) -> None:
    fake_prom.ready = {_DEVICE: 1.0}
    assert _deploy(client, "mv_v1").status_code == 200  # last good

    # The next update can't even fetch a valid package (hash mismatch on download).
    _StatefulDeployer.fail_cache = ValueError("artifact sha256 mismatch")
    resp = _deploy(client, "mv_v2")

    assert resp.status_code == 502
    assert _Nano.active == "mv_v1"  # unchanged — nothing was pushed
    assert _Nano.history == ["mv_v1"]


def test_interrupted_push_keeps_last_good_version(client, fake_prom) -> None:
    fake_prom.ready = {_DEVICE: 1.0}
    assert _deploy(client, "mv_v1").status_code == 200

    # Package fetched fine, but the nano connection drops mid-upload.
    _StatefulDeployer.fail_push = httpx2.HTTPError("connection reset during upload")
    resp = _deploy(client, "mv_v2")

    assert resp.status_code == 502
    assert _Nano.active == "mv_v1"  # the half-finished push did not take effect
    assert _Nano.history == ["mv_v1"]


def test_unknown_device_deploy_does_not_touch_nano(client, fake_prom) -> None:
    fake_prom.ready = {}  # device not in fleet view
    resp = _deploy(client, "mv_v1")
    assert resp.status_code == 404
    assert _Nano.active is None and _Nano.history == []


# --- deployer-level integration: the REAL multipart push against an in-process nano -----

def _package_on_disk(tmp_path: Path, model_id: str, onnx: bytes) -> CachedModelPackage:
    import hashlib

    digest = hashlib.sha256(onnx).hexdigest()
    manifest = {
        "model_version_id": model_id, "model_id": model_id, "name": "YOLOv12 MT",
        "git_sha": None, "weights_hash": digest, "artifact_filename": "model.onnx",
        "nvinfer_config_filename": None, "shards": [],
    }
    pkg = tmp_path / f"{model_id}.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("model.onnx", onnx)
    pkg.write_bytes(buf.getvalue())
    return CachedModelPackage(path=pkg, sha256="0" * 64, manifest=model_deploy._read_manifest(pkg))


class _HttpResponse:
    def __init__(self, payload, status_error=None):
        self._payload, self._err = payload, status_error

    def raise_for_status(self):
        if self._err is not None:
            raise self._err

    def json(self):
        return self._payload


def test_push_rollback_sequence_updates_then_restores(tmp_path: Path, monkeypatch) -> None:
    """v1 → v2 → v1 through ModelDeployer.push_to_nano's real upload code."""
    nano = {"active": None, "history": []}

    def fake_put(url, *, headers, files, timeout):
        _, fh, _ = files["file"]
        fh.seek(0)
        with zipfile.ZipFile(io.BytesIO(fh.read())) as zf:
            manifest = json.loads(zf.read("manifest.json"))
        nano["active"] = manifest["model_id"]  # the nano installs what fleet uploaded
        nano["history"].append(manifest["model_id"])
        return _HttpResponse({
            "model_id": manifest["model_id"], "weights_hash": manifest["weights_hash"],
            "artifact_filename": manifest["artifact_filename"], "nvinfer_config_filename": None,
        })

    monkeypatch.setattr(model_deploy.httpx2, "put", fake_put)
    deployer = ModelDeployer(catalog_url="http://c/api/v1", cache_dir=tmp_path)
    v1 = _package_on_disk(tmp_path, "mv_v1", b"weights-one")
    v2 = _package_on_disk(tmp_path, "mv_v2", b"weights-two-different")

    assert deployer.push_to_nano(v1, "http://nano:8000").model_id == "mv_v1"
    assert nano["active"] == "mv_v1"
    assert deployer.push_to_nano(v2, "http://nano:8000").model_id == "mv_v2"
    assert nano["active"] == "mv_v2"
    assert deployer.push_to_nano(v1, "http://nano:8000").model_id == "mv_v1"  # rollback
    assert nano["active"] == "mv_v1"
    assert nano["history"] == ["mv_v1", "mv_v2", "mv_v1"]


def test_push_failure_leaves_nano_on_prior_version(tmp_path: Path, monkeypatch) -> None:
    nano = {"active": "mv_v1"}  # already running v1

    def fake_put(url, *, headers, files, timeout):
        return _HttpResponse({}, status_error=httpx2.HTTPError("nano 503 mid-upload"))

    monkeypatch.setattr(model_deploy.httpx2, "put", fake_put)
    deployer = ModelDeployer(catalog_url="http://c/api/v1", cache_dir=tmp_path)
    v2 = _package_on_disk(tmp_path, "mv_v2", b"weights-two")

    with pytest.raises(httpx2.HTTPError):
        deployer.push_to_nano(v2, "http://nano:8000")
    assert nano["active"] == "mv_v1"  # failed update did not advance the version


# --- the inference-image deploy path rolls back the same way ----------------------------

def _set_image(client, image: str):
    return client.post(
        f"/api/fleet/devices/{_DEVICE}/inference/image", json={"image": image}
    )


def test_image_rollback_repatches_prior_tag(client, fake_prom, fake_k8s) -> None:
    fake_prom.ready = {_DEVICE: 1.0}
    good = "registry.endoscopeai.com/eai-nano/inference:v1"
    bad = "registry.endoscopeai.com/eai-nano/inference:v2"

    assert _set_image(client, good).status_code == 200
    assert _set_image(client, bad).status_code == 200
    assert _set_image(client, good).status_code == 200  # roll back to v1

    applied = [p[3] for p in fake_k8s.patches]
    assert applied == [good, bad, good]


def test_failed_image_patch_preserves_last_good(client, fake_prom, fake_k8s) -> None:
    from app.k8s import KubernetesUnavailable

    fake_prom.ready = {_DEVICE: 1.0}
    good = "registry.endoscopeai.com/eai-nano/inference:v1"
    assert _set_image(client, good).status_code == 200

    # The next patch fails at the k8s API — the last good image must remain applied.
    fake_k8s.fail = KubernetesUnavailable("apiserver 500")
    resp = _set_image(client, "registry.endoscopeai.com/eai-nano/inference:v2")
    assert resp.status_code == 502

    applied = [p[3] for p in fake_k8s.patches]
    assert applied == [good]  # no v2 patch recorded

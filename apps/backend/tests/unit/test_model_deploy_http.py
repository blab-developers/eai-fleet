"""ModelDeployer HTTP loop tests — the catalog fetch and the nano push.

The manifest/hash *parsing* is covered by test_model_deploy.py; this module covers
the two HTTP seams (``cache_package`` GET from catalog, ``push_to_nano`` PUT to
nano) with httpx2 mocked, so the real streaming-to-cache, atomic rename, hash
verification, and multipart upload run without a live catalog or nano.
"""

import hashlib
import io
import json
import zipfile
from pathlib import Path

import httpx2
import pytest

from app import model_deploy
from app.model_deploy import ModelDeployer

_ONNX = b"\x08\x01fake-yolo12-onnx-weights"
_HASH = hashlib.sha256(_ONNX).hexdigest()


def _package_bytes(*, weights_hash: str = _HASH) -> bytes:
    """An in-memory catalog package: manifest.json + the .onnx artifact."""
    manifest = {
        "model_version_id": "mv_123",
        "model_id": "mv_123",
        "name": "YOLOv12 MT",
        "git_sha": None,
        "weights_hash": weights_hash,
        "artifact_filename": "yolo12-mt.onnx",
        "nvinfer_config_filename": None,
        "shards": [{"uri": "s3://eai/final/shard-000001.tar", "sha256": "a" * 64}],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("yolo12-mt.onnx", _ONNX)
    return buf.getvalue()


class _FakeStream:
    """Context-manager stand-in for ``httpx2.stream(...)``."""

    def __init__(self, body: bytes, *, status_error: Exception | None = None) -> None:
        self._body = body
        self._status_error = status_error

    def __enter__(self) -> "_FakeStream":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def raise_for_status(self) -> None:
        if self._status_error is not None:
            raise self._status_error

    def iter_bytes(self, chunk: int):
        for i in range(0, len(self._body), chunk):
            yield self._body[i : i + chunk]


class _FakeResponse:
    """Stand-in for the ``httpx2.put`` response."""

    def __init__(self, payload: dict, *, status_error: Exception | None = None) -> None:
        self._payload = payload
        self._status_error = status_error

    def raise_for_status(self) -> None:
        if self._status_error is not None:
            raise self._status_error

    def json(self) -> dict:
        return self._payload


def test_cache_package_streams_verifies_and_caches(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_stream(method, url, *, headers, timeout):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        return _FakeStream(_package_bytes())

    monkeypatch.setattr(model_deploy.httpx2, "stream", fake_stream)
    deployer = ModelDeployer(catalog_url="http://catalog:8000/api/v1", cache_dir=tmp_path)

    cached = deployer.cache_package("mv_123")

    # Hit the right catalog endpoint and persisted the verified package.
    assert captured["method"] == "GET"
    assert captured["url"] == "http://catalog:8000/api/v1/models/mv_123/package"
    assert cached.path == tmp_path / "mv_123" / "package.zip"
    assert cached.path.exists()
    assert not cached.path.with_suffix(".zip.part").exists()  # atomic rename happened
    assert cached.manifest.model_id == "mv_123"
    assert cached.sha256 == hashlib.sha256(_package_bytes()).hexdigest()


def test_cache_package_hash_mismatch_raises_and_leaves_no_final(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        model_deploy.httpx2,
        "stream",
        lambda *a, **k: _FakeStream(_package_bytes(weights_hash="b" * 64)),
    )
    deployer = ModelDeployer(catalog_url="http://catalog/api/v1", cache_dir=tmp_path)

    with pytest.raises(ValueError, match="artifact sha256 mismatch"):
        deployer.cache_package("mv_123")
    # A corrupt download must not leave a usable package.zip behind.
    assert not (tmp_path / "mv_123" / "package.zip").exists()


def test_cache_package_sends_bearer_when_token_set(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_stream(method, url, *, headers, timeout):
        captured["headers"] = headers
        return _FakeStream(_package_bytes())

    monkeypatch.setattr(model_deploy.httpx2, "stream", fake_stream)
    ModelDeployer(
        catalog_url="http://c/api/v1", cache_dir=tmp_path, catalog_token="sekret"
    ).cache_package("mv_123")
    assert captured["headers"] == {"Authorization": "Bearer sekret"}


def test_push_to_nano_uploads_multipart_and_parses_response(tmp_path: Path, monkeypatch) -> None:
    # A verified cached package on disk.
    pkg = tmp_path / "package.zip"
    pkg.write_bytes(_package_bytes())
    cached = model_deploy.CachedModelPackage(
        path=pkg, sha256=_HASH, manifest=model_deploy._read_manifest(pkg)
    )

    captured: dict[str, object] = {}

    def fake_put(url, *, headers, files, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["file_field"] = "file" in files
        return _FakeResponse(
            {
                "model_id": "mv_123",
                "weights_hash": _HASH,
                "artifact_filename": "yolo12-mt.onnx",
                "nvinfer_config_filename": None,
            }
        )

    monkeypatch.setattr(model_deploy.httpx2, "put", fake_put)
    deployer = ModelDeployer(catalog_url="http://c/api/v1", cache_dir=tmp_path)

    install = deployer.push_to_nano(cached, "http://nano:8500/", nano_token="tok")

    assert captured["url"] == "http://nano:8500/api/models/package"
    assert captured["headers"] == {"Authorization": "Bearer tok"}
    assert captured["file_field"] is True
    assert install.model_id == "mv_123"
    assert install.weights_hash == _HASH


def test_push_to_nano_propagates_http_error(tmp_path: Path, monkeypatch) -> None:
    pkg = tmp_path / "package.zip"
    pkg.write_bytes(_package_bytes())
    cached = model_deploy.CachedModelPackage(
        path=pkg, sha256=_HASH, manifest=model_deploy._read_manifest(pkg)
    )
    err = httpx2.HTTPError("nano refused")
    monkeypatch.setattr(
        model_deploy.httpx2, "put", lambda *a, **k: _FakeResponse({}, status_error=err)
    )
    deployer = ModelDeployer(catalog_url="http://c/api/v1", cache_dir=tmp_path)

    with pytest.raises(httpx2.HTTPError, match="nano refused"):
        deployer.push_to_nano(cached, "http://nano:8500")

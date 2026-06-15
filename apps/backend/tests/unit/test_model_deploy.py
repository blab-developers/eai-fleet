"""Model package deployment core tests."""

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from app.model_deploy import _read_manifest, _verify_artifact_hash

_ONNX = b"\x08\x01fake-yolo12-onnx"


def _write_package(path: Path, *, weights_hash: str) -> None:
    manifest = {
        "model_version_id": "mv_123",
        "model_id": "mv_123",
        "name": "YOLOv12 MT",
        "weights_hash": weights_hash,
        "artifact_filename": "yolo12-mt.onnx",
        "nvinfer_config_filename": None,
        "shards": [{"uri": "s3://eai/final/shard-000001.tar", "sha256": "a" * 64}],
    }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("yolo12-mt.onnx", _ONNX)


def test_package_manifest_and_artifact_hash_verify(tmp_path: Path) -> None:
    package = tmp_path / "package.zip"
    _write_package(package, weights_hash=hashlib.sha256(_ONNX).hexdigest())

    manifest = _read_manifest(package)
    _verify_artifact_hash(package, manifest)

    assert manifest.model_id == "mv_123"


def test_package_artifact_hash_mismatch_raises(tmp_path: Path) -> None:
    package = tmp_path / "package.zip"
    _write_package(package, weights_hash="b" * 64)

    manifest = _read_manifest(package)
    with pytest.raises(ValueError, match="artifact sha256 mismatch"):
        _verify_artifact_hash(package, manifest)

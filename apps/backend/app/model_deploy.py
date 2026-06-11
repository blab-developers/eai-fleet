"""Model package deployment core — catalog cache then push to one nano backend.

Fleet remains stateless: the cached package file is the receipt. Given a catalog
model version id and a reachable nano backend URL, this module downloads the
package from eai-catalog, verifies the embedded artifact hash from manifest.json,
and uploads that same package to nano.
"""

import hashlib
import json
import zipfile
from pathlib import Path

import httpx2
from pydantic import BaseModel, ConfigDict, Field

_CHUNK = 1024 * 1024


class ModelPackageShard(BaseModel):
    """Shard provenance embedded in a catalog model package manifest."""

    model_config = ConfigDict(extra="forbid")

    uri: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    size_bytes: int | None = Field(default=None, ge=0)
    sample_count: int | None = Field(default=None, ge=0)
    observation_count: int | None = Field(default=None, ge=0)
    split: str | None = None
    notes: str | None = None


class ModelPackageManifest(BaseModel):
    """manifest.json written by eai-catalog into each package."""

    model_config = ConfigDict(extra="forbid")

    model_version_id: str
    model_id: str
    name: str
    git_sha: str | None = None
    weights_hash: str
    artifact_filename: str
    nvinfer_config_filename: str | None = None
    shards: list[ModelPackageShard]


class CachedModelPackage(BaseModel):
    """Verified cached package ready to push to nano."""

    model_config = ConfigDict(extra="forbid")

    path: Path
    sha256: str
    manifest: ModelPackageManifest


class NanoModelInstall(BaseModel):
    """Nano backend's install response."""

    model_config = ConfigDict(extra="forbid")

    model_id: str
    weights_hash: str
    artifact_filename: str
    nvinfer_config_filename: str | None = None


class ModelDeployer:
    """Downloads verified catalog packages and pushes them to eai-nano."""

    def __init__(
        self,
        catalog_url: str,
        cache_dir: Path,
        catalog_token: str = "",
        timeout_s: float = 60.0,
    ) -> None:
        self._catalog_url = catalog_url.rstrip("/")
        self._cache_dir = cache_dir
        self._catalog_headers = _headers(catalog_token)
        self._timeout_s = timeout_s

    def cache_package(self, model_version_id: str) -> CachedModelPackage:
        """Download and verify a catalog model package into the local cache."""
        dest_dir = self._cache_dir / model_version_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        part = dest_dir / "package.zip.part"
        dest = dest_dir / "package.zip"
        with httpx2.stream(
            "GET",
            f"{self._catalog_url}/models/{model_version_id}/package",
            headers=self._catalog_headers,
            timeout=self._timeout_s,
        ) as resp:
            resp.raise_for_status()
            with part.open("wb") as fh:
                for chunk in resp.iter_bytes(_CHUNK):
                    fh.write(chunk)
        manifest = _read_manifest(part)
        _verify_artifact_hash(part, manifest)
        part.replace(dest)
        return CachedModelPackage(path=dest, sha256=_sha256(dest), manifest=manifest)

    def push_to_nano(
        self, cached: CachedModelPackage, nano_base_url: str, nano_token: str = ""
    ) -> NanoModelInstall:
        """Upload a verified package to the nano backend install endpoint."""
        with cached.path.open("rb") as fh:
            response = httpx2.put(
                f"{nano_base_url.rstrip('/')}/api/models/package",
                headers=_headers(nano_token),
                files={"file": (cached.path.name, fh, "application/zip")},
                timeout=self._timeout_s,
            )
        response.raise_for_status()
        return NanoModelInstall.model_validate(response.json())


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


def _read_manifest(path: Path) -> ModelPackageManifest:
    with zipfile.ZipFile(path) as zf:
        with zf.open("manifest.json") as fh:
            return ModelPackageManifest.model_validate(json.load(fh))


def _verify_artifact_hash(path: Path, manifest: ModelPackageManifest) -> None:
    with zipfile.ZipFile(path) as zf:
        try:
            with zf.open(manifest.artifact_filename) as fh:
                digest = hashlib.sha256()
                for chunk in iter(lambda: fh.read(_CHUNK), b""):
                    digest.update(chunk)
        except KeyError as exc:
            raise ValueError(f"package missing artifact {manifest.artifact_filename!r}") from exc
    actual = digest.hexdigest()
    if actual != manifest.weights_hash:
        raise ValueError(f"artifact sha256 mismatch: expected {manifest.weights_hash}, got {actual}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()

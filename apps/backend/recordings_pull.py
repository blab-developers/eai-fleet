"""Recordings replication — fleet-mgr PULLs each nano's manifest and downloads the delta.

One-way, **central-initiated PULL** (Spec 024): read ``GET /api/recordings/manifest``, diff it
against what is already on disk (by ``media_file_id`` + ``sha256``), then download the missing or
changed files via the ranged ``/api/recordings/sessions/{media_file_id}/{video|sidecar}`` endpoints
and verify the ``sha256``. The nano holds the inbound bearer token; fleet presents it. The nano
pushes nothing, knows nothing of central's layout, and tracks no replication state.

**Stateless by design (matches fleet-mgr — no DB).** The *downloaded files are the receipt*: a file
already present with a matching sha256 is skipped, so re-running is idempotent and exact duplicates
cost nothing. There is no progress/receipt table.

⚠️ **Wiring left to the caller — open infra questions, intentionally not decided here:**
  - how central *reaches* a NAT'd nano's backend ``:8000`` (KubeEdge proxy / tunnel / per-node
    address) — the caller supplies a reachable ``base_url``;
  - how nanos are enumerated (``device_id`` → ``base_url``) — likely from the same
    KubeEdge/Prometheus source the fleet view uses;
  - the bearer ``token`` source (vault — the nano's ``AUTH_SECRET_KEY``);
  - the pull schedule (nightly cron and/or on-demand from the UI).
This module is the pure reconciliation core: given ``(base_url, token, dest_dir)`` it reconciles one
device's recordings.
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path

import httpx2
from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger(__name__)

_CHUNK = 1024 * 1024  # 1 MiB streaming/hash chunk — safe for multi-GB clips


class ManifestFile(BaseModel):
    """One pullable physical file, as the nano reports it (mirrors eai-nano's ManifestFile)."""

    model_config = ConfigDict(extra="forbid")

    media_file_id: str
    observation_id: str | None = None
    kind: str  # "video" | "sidecar"
    filename: str
    size_bytes: int = Field(ge=0)
    sha256: str | None = None
    created_at: datetime
    sealed: bool = True


class PullSummary(BaseModel):
    """Outcome of reconciling one device."""

    model_config = ConfigDict(extra="forbid")

    device_files_total: int = Field(ge=0)
    pulled: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)  # already present + sha256 matches (the receipt)
    failed: int = Field(default=0, ge=0)  # download error or sha256 mismatch
    bytes_pulled: int = Field(default=0, ge=0)


def plan_pulls(manifest: list[ManifestFile], dest_dir: Path) -> list[ManifestFile]:
    """The delta to download: sealed, hashed files whose local copy is missing or sha-mismatched.

    Pure (no I/O beyond reading local hashes) so the diff logic is unit-testable without HTTP.
    Files not yet hashed by the nano (``sha256 is None``) are skipped — central re-polls later.
    """
    todo: list[ManifestFile] = []
    for f in manifest:
        if not f.sealed or f.sha256 is None:
            continue
        if _local_sha256(_dest_path(dest_dir, f)) != f.sha256:
            todo.append(f)
    return todo


def _dest_path(dest_dir: Path, f: ManifestFile) -> Path:
    """Where a file lands locally — keyed by media_file_id so renames/collisions can't clobber."""
    return dest_dir / f.media_file_id / f.filename


def _local_sha256(path: Path) -> str | None:
    """sha256 of a local file, or None if it does not exist."""
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


class RecordingsPuller:
    """Reconciles ONE nano's recordings into ``dest_dir`` (fleet owns the layout)."""

    def __init__(
        self,
        base_url: str,
        token: str,
        dest_dir: str | Path,
        timeout_s: float = 30.0,
        page_size: int = 100,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._dest = Path(dest_dir)
        self._timeout_s = timeout_s
        self._page_size = page_size

    def fetch_manifest(self) -> list[ManifestFile]:
        """Read the device's full manifest, following pagination."""
        files: list[ManifestFile] = []
        offset = 0
        while True:
            page = httpx2.get(
                f"{self._base_url}/api/recordings/manifest",
                params={"limit": self._page_size, "offset": offset},
                headers=self._headers,
                timeout=self._timeout_s,
            )
            page.raise_for_status()
            payload = page.json()
            files.extend(ManifestFile(**f) for f in payload["files"])
            offset += self._page_size
            if offset >= payload["total"]:
                return files

    def reconcile(self) -> PullSummary:
        """Pull this device's delta (missing/changed files), verifying sha256. Idempotent."""
        manifest = self.fetch_manifest()
        todo = plan_pulls(manifest, self._dest)
        summary = PullSummary(
            device_files_total=len(manifest),
            skipped=len(manifest) - len(todo),
        )
        for f in todo:
            try:
                summary.bytes_pulled += self._pull_file(f)
                summary.pulled += 1
            except (httpx2.HTTPError, _ShaMismatch) as e:
                log.warning("pull failed for %s (%s): %s", f.media_file_id, f.filename, e)
                summary.failed += 1
        return summary

    def _pull_file(self, f: ManifestFile) -> int:
        """Download one file (ranged/resumable) and verify sha256. Returns bytes written."""
        endpoint = "video" if f.kind == "video" else "sidecar"
        url = f"{self._base_url}/api/recordings/sessions/{f.media_file_id}/{endpoint}"
        dest = _dest_path(self._dest, f)
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_suffix(dest.suffix + ".part")

        # Resume a previous partial download with an HTTP Range request.
        have = part.stat().st_size if part.exists() else 0
        headers = dict(self._headers)
        if have:
            headers["Range"] = f"bytes={have}-"

        written = have
        with httpx2.stream("GET", url, headers=headers, timeout=self._timeout_s) as resp:
            resp.raise_for_status()
            mode = "ab" if (have and resp.status_code == 206) else "wb"
            if mode == "wb":
                written = 0  # server ignored Range (200) → restart cleanly
            with open(part, mode) as fh:
                for chunk in resp.iter_bytes(_CHUNK):
                    fh.write(chunk)
                    written += len(chunk)

        actual = _local_sha256(part)
        if f.sha256 is not None and actual != f.sha256:
            part.unlink(missing_ok=True)
            raise _ShaMismatch(f"sha256 mismatch: expected {f.sha256}, got {actual}")
        part.replace(dest)  # atomic promote once verified
        return written


class _ShaMismatch(RuntimeError):
    """A downloaded file's sha256 did not match the manifest — discarded."""

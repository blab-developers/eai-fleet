"""Recordings replication — fleet-mgr PULLs each nano's saved sessions and downloads new ones.

One-way, **central-initiated PULL** (Spec 024): list ``GET /api/sessions/saved`` (paginated),
then download the pristine MP4 and the NDJSON detection sidecar for each session it doesn't
already have, via ``GET /api/sessions/{inference_id}/{video|sidecar}``. The nano holds the
inbound bearer token; fleet presents it. The nano pushes nothing and knows nothing of central's
layout.

**Stateless by design (matches fleet-mgr — no DB).** The *downloaded files are the receipt*: a
session whose files are already present on disk is skipped, so re-running is idempotent. Saved
(terminal) sessions are immutable — the nano excludes the still-recording session from
``/saved`` — so "file exists locally" is a safe skip condition (the nano list carries no sha256
or size to diff on).

Layout under ``dest_dir``: ``<inference_id>/<inference_id>.mp4`` + ``<inference_id>.ndjson``.
The eai-catalog device-prediction ingest globs ``**/*.ndjson`` and pairs each sidecar with its
sibling ``.mp4`` (matching the catalog VIDEO by the mp4 sha256), so the per-session filename is
immaterial — only the mp4+ndjson pairing in one directory matters.

⚠️ **Wiring left to the caller — open infra questions, intentionally not decided here:**
  - how central *reaches* a NAT'd nano's backend ``:8000`` (KubeEdge proxy / tunnel / per-node
    address) — the caller supplies a reachable ``base_url``;
  - the bearer ``token`` source (vault — the nano's ``AUTH_SECRET_KEY``);
  - the pull schedule (a k8s CronJob hitting the endpoint, or an on-demand UI/script call).
This module is the pure reconciliation core: given ``(base_url, token, dest_dir)`` it reconciles
one device's saved sessions.
"""

import logging
from datetime import datetime
from pathlib import Path

import httpx2
from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger(__name__)

_CHUNK = 1024 * 1024  # 1 MiB streaming chunk — safe for multi-GB clips


class SavedSession(BaseModel):
    """One saved session as the nano reports it (subset of eai-nano's SavedSession).

    ``extra="ignore"`` so the nano can add fields without breaking the pull.
    """

    model_config = ConfigDict(extra="ignore")

    inference_id: str
    has_sidecar: bool = False
    started_at: datetime | None = None


class PullSummary(BaseModel):
    """Outcome of reconciling one device."""

    model_config = ConfigDict(extra="forbid")

    sessions_total: int = Field(default=0, ge=0)
    pulled: int = Field(default=0, ge=0)  # files downloaded this run
    skipped: int = Field(default=0, ge=0)  # files already present (the receipt)
    failed: int = Field(default=0, ge=0)  # download error
    bytes_pulled: int = Field(default=0, ge=0)


class RecordingsPuller:
    """Reconciles ONE nano's saved sessions into ``dest_dir`` (fleet owns the layout)."""

    def __init__(
        self,
        base_url: str,
        token: str,
        dest_dir: str | Path,
        timeout_s: float = 30.0,
        page_size: int = 100,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._dest = Path(dest_dir)
        self._timeout_s = timeout_s
        self._page_size = page_size

    def fetch_sessions(self) -> list[SavedSession]:
        """Read the device's full saved-session list, following pagination."""
        sessions: list[SavedSession] = []
        offset = 0
        while True:
            page = httpx2.get(
                f"{self._base_url}/api/sessions/saved",
                params={"limit": self._page_size, "offset": offset},
                headers=self._headers,
                timeout=self._timeout_s,
            )
            page.raise_for_status()
            payload = page.json()
            sessions.extend(SavedSession(**item) for item in payload["items"])
            offset += self._page_size
            if offset >= payload["total"] or not payload["items"]:
                return sessions

    def reconcile(self) -> PullSummary:
        """Pull each saved session's mp4 (+ sidecar) that isn't already on disk. Idempotent."""
        sessions = self.fetch_sessions()
        summary = PullSummary(sessions_total=len(sessions))
        for session in sessions:
            kinds = ["video"] + (["sidecar"] if session.has_sidecar else [])
            for kind in kinds:
                dest = self._dest_path(session.inference_id, kind)
                if dest.exists():
                    summary.skipped += 1
                    continue
                try:
                    summary.bytes_pulled += self._pull_file(session.inference_id, kind, dest)
                    summary.pulled += 1
                except httpx2.HTTPError as e:
                    log.warning("pull failed for %s (%s): %s", session.inference_id, kind, e)
                    summary.failed += 1
        return summary

    def _dest_path(self, inference_id: str, kind: str) -> Path:
        """Where a file lands locally — one directory per session, sibling mp4 + ndjson."""
        suffix = ".mp4" if kind == "video" else ".ndjson"
        return self._dest / inference_id / f"{inference_id}{suffix}"

    def _pull_file(self, inference_id: str, kind: str, dest: Path) -> int:
        """Download one file (ranged/resumable) to ``dest``. Returns bytes written."""
        url = f"{self._base_url}/api/sessions/{inference_id}/{kind}"
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

        part.replace(dest)  # atomic promote once fully written
        return written

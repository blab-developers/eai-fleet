"""Client for one eai-nano backend — the fleet's outbound calls to a device.

The fleet is stateless (Spec 008: no device→URL map), so a nano's reachable ``base_url``
(+ optional token) is caller-supplied per call, mirroring ``ModelDeployer`` /
``RecordingsPuller``. Today this covers the pre-image-change graceful-shutdown handshake:
before the fleet patches the inference image, it asks the nano to drain so no session
state (an in-progress recording) is lost.

The nano contract (implemented in eai-nano as a follow-up):
    POST {base_url}/api/admin/prepare-shutdown  → 200 {drained, recordings_finalized,
    pipeline_stopped}. The nano finalizes any active recording (mp4 + sidecar) and stops
    the pipeline, then confirms.
"""

import httpx2
from pydantic import BaseModel, ConfigDict, ValidationError


class NanoUnavailable(RuntimeError):
    """The nano backend could not be reached, refused, or gave an unusable response."""


class ShutdownAck(BaseModel):
    """The nano's response to prepare-shutdown — its confirmation that it drained."""

    model_config = ConfigDict(extra="ignore")

    drained: bool
    recordings_finalized: int = 0
    pipeline_stopped: bool = False


class NanoClient:
    """Thin client over one nano backend's admin API."""

    def __init__(self, base_url: str, token: str = "", timeout_s: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._timeout = timeout_s

    def prepare_shutdown(self) -> ShutdownAck:
        """Ask the nano to drain before an image swap; return its ack.

        Raises ``NanoUnavailable`` if the nano can't be reached or returns something
        unusable — the caller must then NOT proceed with the image change.
        """
        url = f"{self._base_url}/api/admin/prepare-shutdown"
        try:
            resp = httpx2.post(url, headers=self._headers, timeout=self._timeout)
            resp.raise_for_status()
            payload = resp.json()
        except (httpx2.HTTPError, ValueError) as e:
            raise NanoUnavailable(f"nano prepare-shutdown request failed: {e}") from e
        try:
            return ShutdownAck.model_validate(payload)
        except ValidationError as e:
            raise NanoUnavailable(f"nano prepare-shutdown returned an unexpected shape: {e}") from e

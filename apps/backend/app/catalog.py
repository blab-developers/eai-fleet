"""Read-through to eai-catalog — the source of truth for available model versions.

The fleet keeps no model state (Spec 008): the model selector is populated live from the
central eai-catalog. This is the LIST side; the download-then-push side (deploying one
version's package to a nano) lives in ``model_deploy.py``. Both target the same
``catalog_url``.
"""

import httpx2

from app.models import ModelVersionView


class CatalogUnavailable(RuntimeError):
    """eai-catalog could not be queried — the model list can't be derived."""


class CatalogClient:
    """Thin read client over the eai-catalog model-version API (``GET /models``)."""

    def __init__(self, base_url: str, token: str = "", timeout_s: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._timeout = timeout_s

    def list_models(self) -> list[ModelVersionView]:
        """Every available model version, newest first (catalog order preserved)."""
        url = f"{self._base_url}/models"
        try:
            resp = httpx2.get(url, headers=self._headers, timeout=self._timeout)
            resp.raise_for_status()
            payload = resp.json()
        except (httpx2.HTTPError, ValueError) as e:
            raise CatalogUnavailable(f"eai-catalog query failed: {e}") from e
        if not isinstance(payload, list):
            raise CatalogUnavailable(
                f"eai-catalog /models returned {type(payload).__name__}, expected a list"
            )
        return [_to_view(entry) for entry in payload if isinstance(entry, dict)]


def _to_view(entry: dict) -> ModelVersionView:
    """Project a catalog ModelVersion dict onto the fields the fleet UI needs.

    The catalog returns more fields than the selector uses (shards, class_map, …); we take
    only what the UI shows + the id needed to deploy, ignoring the rest.
    """
    return ModelVersionView(
        id=str(entry["id"]),
        name=str(entry.get("name", entry["id"])),
        git_sha=entry.get("git_sha"),
        jetson_device_target=entry.get("jetson_device_target"),
        weights_hash=entry.get("weights_hash"),
        created_at=entry.get("created_at"),
        notes=entry.get("notes"),
    )

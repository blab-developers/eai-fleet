"""CatalogClient parsing — the real read against canned eai-catalog JSON.

The route tests use a FakeCatalog; these exercise the REAL ``CatalogClient.list_models``
(field projection, non-dict filtering, error mapping) with the HTTP layer stubbed. No
live catalog. Mirrors the field shape the live ``GET /api/v1/models`` returns.
"""

import pytest

from app import catalog as catalog_mod
from app.catalog import CatalogClient, CatalogUnavailable, _to_view


class _Resp:
    def __init__(self, payload, status_error=None):
        self._payload, self._err = payload, status_error

    def raise_for_status(self):
        if self._err is not None:
            raise self._err

    def json(self):
        return self._payload


def test_to_view_projects_fields_and_ignores_extras() -> None:
    # A catalog ModelVersion carries more than the selector needs (shards, class_map, …).
    entry = {
        "id": "abc",
        "name": "orin-approach-C-multitask",
        "git_sha": "jetson-orin-external-v1",
        "jetson_device_target": "orin-nano",
        "weights_hash": "deadbeef",
        "created_at": "2026-06-16T20:32:13",
        "notes": "Approach C",
        "class_map": None,
        "artifact_filename": "yolov12n.onnx",
        "artifact_size_bytes": 1287792,
    }
    view = _to_view(entry)
    assert view.id == "abc"
    assert view.name == "orin-approach-C-multitask"
    assert view.jetson_device_target == "orin-nano"
    assert view.weights_hash == "deadbeef"


def test_to_view_falls_back_name_to_id_when_missing() -> None:
    assert _to_view({"id": "only-id"}).name == "only-id"


def test_list_models_parses_and_filters_non_dicts(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [
        {"id": "mv-1", "name": "one"},
        "garbage",  # a stray non-dict entry must be skipped, not crash
        {"id": "mv-2", "name": "two"},
    ]
    monkeypatch.setattr(catalog_mod.httpx2, "get", lambda url, headers, timeout: _Resp(payload))
    models = CatalogClient("http://catalog/api/v1").list_models()
    assert [m.id for m in models] == ["mv-1", "mv-2"]


def test_list_models_non_list_payload_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        catalog_mod.httpx2, "get", lambda url, headers, timeout: _Resp({"detail": "nope"})
    )
    with pytest.raises(CatalogUnavailable, match="expected a list"):
        CatalogClient("http://catalog/api/v1").list_models()


def test_list_models_http_error_maps_to_catalog_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx2

    def boom(url, headers, timeout):
        raise httpx2.HTTPError("connect timeout")

    monkeypatch.setattr(catalog_mod.httpx2, "get", boom)
    with pytest.raises(CatalogUnavailable):
        CatalogClient("http://catalog/api/v1").list_models()

"""Model-selector list endpoint (task: model selector in the fleet UI).

``GET /api/fleet/models`` is the fleet UI's source for "all available models" — a
read-through to eai-catalog (the source of truth; the fleet keeps no model state). The
selector shows these; each entry's ``id`` is what the deploy route takes.
"""

from fastapi.testclient import TestClient

from app.catalog import CatalogUnavailable
from app.models import ModelVersionView
from tests.conftest import FakeCatalog


def test_list_models_returns_catalog_versions(
    client: TestClient, fake_catalog: FakeCatalog
) -> None:
    fake_catalog.models = [
        ModelVersionView(
            id="mv-1", name="orin-approach-C", git_sha="abc123", jetson_device_target="orin-nano"
        ),
        ModelVersionView(id="mv-2", name="fleet-rollback-test-v2"),
    ]

    response = client.get("/api/fleet/models")

    assert response.status_code == 200
    body = response.json()
    assert [m["id"] for m in body] == ["mv-1", "mv-2"]
    assert body[0]["name"] == "orin-approach-C"
    assert body[0]["jetson_device_target"] == "orin-nano"
    # Optional fields absent on the second model come back as null, not missing.
    assert body[1]["git_sha"] is None


def test_list_models_empty_is_ok(client: TestClient, fake_catalog: FakeCatalog) -> None:
    fake_catalog.models = []

    response = client.get("/api/fleet/models")

    assert response.status_code == 200
    assert response.json() == []


def test_list_models_502_when_catalog_unavailable(
    client: TestClient, fake_catalog: FakeCatalog
) -> None:
    fake_catalog.fail = CatalogUnavailable("eai-catalog query failed: connect timeout")

    response = client.get("/api/fleet/models")

    assert response.status_code == 502
    assert "catalog" in response.json()["detail"].lower()

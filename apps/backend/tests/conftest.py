"""Test fixtures — a fake Prometheus + fake k8s, no Docker, no cluster.

The fleet view is derived from Prometheus (Spec 008), so tests inject a fake client
that returns canned instant-query maps; the router + ``build_fleet_view`` logic is
exercised end-to-end without a live Prometheus.

The image-set endpoint also takes a k8s client dependency; tests inject a fake that
records the PATCH it would have made instead of touching a real cluster.
"""

import pytest
from fastapi.testclient import TestClient

from app.catalog import CatalogUnavailable
from app.k8s import KubernetesUnavailable
from app.main import app
from app.models import ModelVersionView
from app.prometheus import PrometheusUnavailable
from app.routers.fleet import get_catalog, get_k8s, get_prometheus


class FakePrometheus:
    """Stands in for ``PrometheusClient`` with canned per-query data."""

    def __init__(self) -> None:
        self.ready: dict[str, float] = {}  # {node: 1.0/0.0}
        self.gauges: dict[str, dict[str, float]] = {}  # {metric: {device_id: value}}
        self.fail = False

    def node_ready(self) -> dict[str, float]:
        if self.fail:
            raise PrometheusUnavailable("boom")
        return self.ready

    def gauge_by_device(self, metric: str) -> dict[str, float]:
        if self.fail:
            raise PrometheusUnavailable("boom")
        return self.gauges.get(metric, {})


class FakeK8s:
    """Stands in for ``K8sClient`` — records mutations, returns canned reads."""

    def __init__(self) -> None:
        # (namespace, name, container, image) tuples in call order.
        self.patches: list[tuple[str, str, str, str]] = []
        # (namespace, name) tuples for each restart, in call order.
        self.restarts: list[tuple[str, str]] = []
        self.fail: KubernetesUnavailable | None = None
        # Canned reads for the running-image + rollback paths.
        self.current_image: str = "registry.endoscopeai.com/eai-nano/inference:v2"
        # None ⇒ no prior revision (rollback then surfaces a 502, like the real client).
        self.previous_image: str | None = "registry.endoscopeai.com/eai-nano/inference:v1"

    def patch_daemonset_image(
        self,
        namespace: str,
        name: str,
        container: str,
        image: str,
    ) -> None:
        if self.fail is not None:
            raise self.fail
        self.patches.append((namespace, name, container, image))

    def get_daemonset_image(self, namespace: str, name: str, container: str) -> str:
        if self.fail is not None:
            raise self.fail
        return self.current_image

    def restart_daemonset(self, namespace: str, name: str) -> None:
        if self.fail is not None:
            raise self.fail
        self.restarts.append((namespace, name))

    def previous_daemonset_image(self, namespace: str, name: str, container: str) -> str:
        if self.fail is not None:
            raise self.fail
        if self.previous_image is None:
            raise KubernetesUnavailable(
                f"no prior revision of DaemonSet {namespace}/{name} to roll back to"
            )
        return self.previous_image


class FakeCatalog:
    """Stands in for ``CatalogClient`` — returns canned model versions."""

    def __init__(self) -> None:
        self.models: list[ModelVersionView] = []
        self.fail: CatalogUnavailable | None = None

    def list_models(self) -> list[ModelVersionView]:
        if self.fail is not None:
            raise self.fail
        return self.models


@pytest.fixture
def fake_prom() -> FakePrometheus:
    """The canned Prometheus a test configures before calling the API."""
    return FakePrometheus()


@pytest.fixture
def fake_k8s() -> FakeK8s:
    """The canned k8s client a test configures before calling the API."""
    return FakeK8s()


@pytest.fixture
def fake_catalog() -> FakeCatalog:
    """The canned catalog a test configures before calling the API."""
    return FakeCatalog()


@pytest.fixture
def client(fake_prom: FakePrometheus, fake_k8s: FakeK8s, fake_catalog: FakeCatalog):
    """TestClient with the Prometheus, k8s, and catalog dependencies overridden by fakes."""
    app.dependency_overrides[get_prometheus] = lambda: fake_prom
    app.dependency_overrides[get_k8s] = lambda: fake_k8s
    app.dependency_overrides[get_catalog] = lambda: fake_catalog
    yield TestClient(app)
    app.dependency_overrides.clear()

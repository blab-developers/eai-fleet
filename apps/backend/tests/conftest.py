"""Test fixtures — a fake Prometheus + fake k8s, no Docker, no cluster.

The fleet view is derived from Prometheus (Spec 008), so tests inject a fake client
that returns canned instant-query maps; the router + ``build_fleet_view`` logic is
exercised end-to-end without a live Prometheus.

The image-set endpoint also takes a k8s client dependency; tests inject a fake that
records the PATCH it would have made instead of touching a real cluster.
"""

import pytest
from fastapi.testclient import TestClient

from app.k8s import KubernetesUnavailable
from app.main import app
from app.metrics import PrometheusUnavailable
from app.routers.fleet import get_k8s, get_prometheus


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
    """Stands in for ``K8sClient`` — records the patch it would have made."""

    def __init__(self) -> None:
        # (namespace, name, container, image) tuples in call order.
        self.patches: list[tuple[str, str, str, str]] = []
        self.fail: KubernetesUnavailable | None = None

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


@pytest.fixture
def fake_prom() -> FakePrometheus:
    """The canned Prometheus a test configures before calling the API."""
    return FakePrometheus()


@pytest.fixture
def fake_k8s() -> FakeK8s:
    """The canned k8s client a test configures before calling the API."""
    return FakeK8s()


@pytest.fixture
def client(fake_prom: FakePrometheus, fake_k8s: FakeK8s):
    """TestClient with both dependencies overridden by fakes."""
    app.dependency_overrides[get_prometheus] = lambda: fake_prom
    app.dependency_overrides[get_k8s] = lambda: fake_k8s
    yield TestClient(app)
    app.dependency_overrides.clear()

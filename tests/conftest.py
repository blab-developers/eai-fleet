"""Test fixtures — a fake Prometheus, no Docker, no cluster.

The fleet view is derived from Prometheus (Spec 008), so tests inject a fake client
that returns canned instant-query maps; the router + ``build_fleet_view`` logic is
exercised end-to-end without a live Prometheus.
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from prometheus_query import PrometheusUnavailable
from routers.fleet import get_prometheus


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


@pytest.fixture
def fake_prom() -> FakePrometheus:
    """The canned Prometheus a test configures before calling the API."""
    return FakePrometheus()


@pytest.fixture
def client(fake_prom: FakePrometheus):
    """TestClient with the Prometheus dependency overridden by the fake."""
    app.dependency_overrides[get_prometheus] = lambda: fake_prom
    yield TestClient(app)
    app.dependency_overrides.clear()

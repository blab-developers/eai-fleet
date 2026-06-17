"""Prometheus exposition for fleet-mgr itself (Spec 025 §1c parity).

Defines the fleet-mgr collector + its dedicated port (9094); the shared
``eai.metrics.start_metrics_server`` serves it (wired in ``main.lifespan``).
The exporter exposes:
  - eai_fleet_up: fleet-mgr process status (always 1.0)
  - eai_fleet_prometheus_up: central Prometheus connectivity (1.0 / 0.0)
  - eai_fleet_k8s_up: Kubernetes API connectivity (1.0 / 0.0)
"""

from collections.abc import Iterable

import httpx2
from prometheus_client.core import GaugeMetricFamily, Metric
from prometheus_client.registry import Collector

from app.config import settings

METRICS_PORT = 9094


class FleetCollector(Collector):
    """Recomputes fleet-mgr system health metrics on scrape."""

    def collect(self) -> Iterable[Metric]:
        prom_up = 1.0
        k8s_up = 1.0

        # 1. Test central Prometheus connectivity
        try:
            # Simple query to check if Prometheus is answering
            url = f"{settings.prometheus_url.rstrip('/')}/api/v1/query"
            resp = httpx2.get(url, params={"query": "1"}, timeout=settings.prometheus_timeout_s)
            if resp.status_code != 200:
                prom_up = 0.0
        except Exception:  # noqa: BLE001 - scrapes must never raise
            prom_up = 0.0

        # 2. Test Kubernetes API connectivity
        try:
            # Read token to see if it's mounted, check API endpoint
            if settings.kubernetes_token_path.exists():
                token = settings.kubernetes_token_path.read_text().strip()
                headers = {"Authorization": f"Bearer {token}"}
                ca_verify = (
                    str(settings.kubernetes_ca_path)
                    if settings.kubernetes_ca_path.exists()
                    else False
                )
                url = f"{settings.kubernetes_api_url.rstrip('/')}/api"
                resp = httpx2.get(
                    url, headers=headers, verify=ca_verify, timeout=settings.kubernetes_timeout_s
                )
                if resp.status_code != 200:
                    k8s_up = 0.0
            else:
                k8s_up = 0.0
        except Exception:  # noqa: BLE001 - scrapes must never raise
            k8s_up = 0.0

        yield GaugeMetricFamily(
            "eai_fleet_up", "Fleet Manager process is serving (always 1 when scraped).", value=1.0
        )
        yield GaugeMetricFamily(
            "eai_fleet_prometheus_up", "Central Prometheus DB is reachable (1/0).", value=prom_up
        )
        yield GaugeMetricFamily(
            "eai_fleet_k8s_up", "Central Kubernetes API is reachable (1/0).", value=k8s_up
        )

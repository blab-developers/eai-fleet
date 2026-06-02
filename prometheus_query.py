"""Read-through to central Prometheus — the fleet view is DERIVED, not ingested.

fleet-mgr holds no device state (Spec 008). Online/offline comes from **KubeEdge node
status** (surfaced centrally by kube-state-metrics) and telemetry from the nano agents'
remote_written ``eai_inference_*`` series. This module queries the central Prometheus
instant-query HTTP API and returns plain ``{identity: value}`` maps; ``build_fleet_view``
composes them into the fleet view.

⚠️ Cluster-verify the PromQL below. The query *logic* is unit-tested against mocked
Prometheus responses, but the exact series/label names are validated only on a live
cluster with kube-state-metrics + the nano remote_write receiver wired up:
  - ``device_id`` is the agent external label (deploy/50-prometheus-agent.yaml) and is
    assumed equal to the KubeEdge ``node`` name that KSM reports.
  - the nano-node filter label (``label_node_role_eai_nano``) is KSM's sanitized form of
    the ``node-role.eai/nano`` node label the agent DaemonSet selects on.
"""

import logging

import httpx2

from models import DeviceView, FleetHealth, FleetView, InferenceState

log = logging.getLogger(__name__)

# ── PromQL (cluster-verify; see module docstring) ───────────────────────────
# Ready *nano* nodes only — keyed by the `node` label (== device_id).
NODE_READY_QUERY = (
    'kube_node_status_condition{condition="Ready",status="true"} '
    "* on (node) group_left "
    'kube_node_labels{label_node_role_eai_nano="true"}'
)
# Live telemetry — keyed by the `device_id` external label.
FPS_METRIC = "eai_inference_fps"
GPU_METRIC = "eai_inference_gpu_utilization"


class PrometheusClient:
    """Thin client over the Prometheus instant-query API (`/api/v1/query`)."""

    def __init__(self, base_url: str, timeout_s: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    def node_ready(self) -> dict[str, float]:
        """Ready=1 / not=0 per nano node, keyed by the `node` label."""
        return self._scalars_by_label(NODE_READY_QUERY, "node")

    def gauge_by_device(self, metric: str) -> dict[str, float]:
        """Latest value of a gauge per device, keyed by the `device_id` label."""
        return self._scalars_by_label(metric, "device_id")

    def _scalars_by_label(self, promql: str, label: str) -> dict[str, float]:
        """Run an instant query; collapse the result vector to {label_value: float}."""
        url = f"{self._base_url}/api/v1/query"
        try:
            resp = httpx2.get(url, params={"query": promql}, timeout=self._timeout_s)
            resp.raise_for_status()
            payload = resp.json()
        except (httpx2.HTTPError, ValueError) as e:
            raise PrometheusUnavailable(f"Prometheus query failed: {e}") from e
        if payload.get("status") != "success":
            raise PrometheusUnavailable(f"Prometheus returned status={payload.get('status')!r}")
        out: dict[str, float] = {}
        for sample in payload["data"]["result"]:
            key = sample["metric"].get(label)
            if key is None:
                continue  # sample without the identity label — not a fleet device
            out[key] = float(sample["value"][1])
        return out


class PrometheusUnavailable(RuntimeError):
    """Central Prometheus could not be queried — the fleet view can't be derived."""


def build_fleet_view(client: PrometheusClient) -> FleetView:
    """Assemble the fleet view from KubeEdge node status + inference telemetry."""
    ready = client.node_ready()
    fps = client.gauge_by_device(FPS_METRIC)
    gpu = client.gauge_by_device(GPU_METRIC)

    device_ids = sorted(set(ready) | set(fps) | set(gpu))
    devices = [_device_view(d, ready, fps, gpu) for d in device_ids]
    online = sum(1 for v in devices if v.health == FleetHealth.ONLINE)
    return FleetView(devices=devices, total=len(devices), online=online)


def _device_view(
    device_id: str,
    ready: dict[str, float],
    fps: dict[str, float],
    gpu: dict[str, float],
) -> DeviceView:
    """Derive one device's view. Online ← KSM Ready; state ← fps (no state metric)."""
    online = ready.get(device_id, 0.0) >= 1.0
    device_fps = fps.get(device_id, 0.0)
    state = InferenceState.RUNNING if (online and device_fps > 0.0) else InferenceState.STOPPED
    return DeviceView(
        device_id=device_id,
        name=device_id,  # human name/labels can enrich this later (see issue)
        state=state,
        fps=device_fps,
        gpu_utilization=gpu.get(device_id, 0.0),
        health=FleetHealth.ONLINE if online else FleetHealth.OFFLINE,
    )

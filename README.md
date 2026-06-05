# Fleet Manager (eai-nano fleet-mgr)

Central fleet manager for the **eai-nano** Jetson fleet (5–10 nanos managed via
KubeEdge). A small FastAPI service deployed on the eai-infra server: it serves the
**fleet view**, derived from platform signals — it ingests nothing from the nanos.

**NOTE:** This app runs on the **central eai-infra server**, NOT on individual nanos.

## Why it exists

Each nano is a **self-contained appliance** (inference → WebRTC + local recording,
local SQLite). Fleet manager is the **one place** to see all of them: which are online,
their state/fps/gpu. No cloud; it runs on-prem.

The nano sends **no heartbeat** (removed in eai-nano Spec 008). State is **derived**:

| Concern | Source |
|---------|--------|
| Online / offline | **KubeEdge node status** via kube-state-metrics (`kube_node_status_condition`) |
| Telemetry (fps / gpu / state) | **Prometheus** `eai_inference_*` series, remote_written outbound by each nano's agent |
| Dashboards / metrics over time | Grafana (paired container) reading central Prometheus |
| Media (video) | WebRTC, per nano |
| Recording bytes | nano local disk; optional on-prem archive (eai-catalog) |

Both signals are read from **central Prometheus** — so fleet-mgr is a stateless
read-through. It has **no database** and **no heartbeat ingest**.

## API

- `GET /api/fleet/devices` — the fleet view: per-device `health` (online/offline,
  from KubeEdge node status), `state` (running/stopped, derived from frame flow),
  `fps`, and `gpu_utilization`, plus `total`/`online` counts.
- `GET /health`.

> The old `POST /api/fleet/heartbeat` ingest is **retired** (Spec 008). The nano no
> longer pushes device state.

### What's derived vs. missing

- **Identity** is the nano's `device_id` — the external label the node-local Prometheus
  agent stamps on remote_write, assumed equal to the KubeEdge node name.
- **State** has no Prometheus metric yet (it was a heartbeat field). Today only
  `running`/`stopped` are derived from whether the device reports frames; richer state
  needs inference to expose an `eai_inference_state` metric.
- **Human name / location / image_tag** are not yet sourced; `name` defaults to
  `device_id`. They can be layered from KubeEdge node labels later.

## Configure

Environment (12-factor; injected by the eai-infra `eai-fleet` Ansible role):

| Var | Default | Meaning |
|-----|---------|---------|
| `EAI_FLEET_PROMETHEUS_URL` | `http://localhost:9090` | central Prometheus base URL |
| `EAI_FLEET_PROMETHEUS_TIMEOUT_S` | `5.0` | per-query timeout |
| `EAI_FLEET_PORT` | `8088` | HTTP port |
| `EAI_FLEET_LOG_LEVEL` | `INFO` | log level |

## Develop

```bash
pip install -e ".[dev]"
pytest -q                               # fake Prometheus, no Docker, no cluster
ruff check . && pyright .
python -m uvicorn main:app --reload --port 8088
```

## Build & deploy

CI is `validate → build → deploy`: build pushes a config-free image to
`registry.endoscopeai.com/eai-nano/fleet-mgr`; the deploy job triggers eai-infra's
Ansible role (`eai_infra/ansible/roles/eai-fleet/`). **eai-nano builds; eai-infra deploys.**
See eai-nano `specs/008-jetson-nano-fleet/`.

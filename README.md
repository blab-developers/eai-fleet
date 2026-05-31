# Fleet Manager (eai-nano/apps/fleet-mgr)

Central fleet manager for the **eai-nano** Jetson fleet (5–10 nanos managed via
KubeEdge). A small FastAPI service deployed on the eai-infra server: device registry,
heartbeat ingest, and the fleet view.

**NOTE:** This app runs on the **central eai-infra server**, NOT on individual nanos.

## Why it exists

Each nano is a **self-contained appliance** (inference → WebRTC + local recording,
local SQLite). Fleet manager is the **one place** to see and manage all of them:
which are online, their state/fps, names/locations, running image. No cloud; it
runs on-prem.

| Concern | Where |
|---------|-------|
| Device registry + heartbeat + fleet view | **fleet-mgr** (eai-nano/apps/fleet-mgr, runs on central server) |
| Liveness cross-check | KubeEdge k8s Node status |
| Metrics over time | Prometheus + Grafana (eai-infra) |
| Media (video) | WebRTC, per nano |
| Recording bytes | nano local disk; optional on-prem archive (eai-catalog) |

## API

- `POST /api/fleet/heartbeat` — a nano reports `{device_id, name, state, fps, uptime_s, last_error, image_tag}`.
- `GET /api/fleet/devices` — the fleet view with derived `online`/`offline`.
- `GET /health`.

## Develop

```bash
cd apps/fleet-mgr
pip install -e ".[dev]"
pytest tests/ -v                                # in-memory SQLite, no Docker
ruff check src && pyright src                   # lint & type-check
python -m uvicorn nano_fleet.main:app --reload --port 8088  # run locally
```

VSCode: Open `apps/fleet-mgr/.vscode/launch.json` and press F5 to debug.

## Build & deploy

CI is `validate → build → deploy` (mirrors eai-catalog): build pushes a config-free
image to `registry.endoscopeai.com/eai-nano/fleet-mgr`; the deploy job triggers
eai-infra's Ansible role (`eai_infra/ansible/roles/eai-fleet-mgr/`).
**eai-nano builds; eai-infra deploys.**
See `AGENTS.md` and `../specs/fleet-mgr.md`.

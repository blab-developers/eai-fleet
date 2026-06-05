# eai-fleet — central fleet manager for the eai-nano Jetson fleet

Central manager for the **eai-nano** Jetson fleet (5–10 nanos managed via KubeEdge).
Two apps, deployed together on the **central eai-infra server** (NOT on the nanos):

| App | What it is | Port |
|-----|------------|------|
| **apps/backend** | FastAPI fleet-view API — derives state from central Prometheus; one mutating route patches the inference DaemonSet | 8088 |
| **apps/frontend** | SvelteKit + Carbon **live fleet UI** — accordion per device (health/fps/gpu/state) + set-inference-image control + Grafana history links | 3000 |

Time-series **history** (fps/gpu/online trends) lives in the central **Grafana** (eai-infra
`metrics` role); the native frontend is the **live snapshot + controls** and deep-links into it.

## Why it exists

Each nano is a **self-contained appliance** (inference → WebRTC + local recording, local
SQLite). eai-fleet is the **one place** to see all of them and to roll an inference image.

The nano sends **no heartbeat** (removed in eai-nano Spec 008). State is **derived**:

| Concern | Source |
|---------|--------|
| Online / offline | **KubeEdge node status** via kube-state-metrics (`kube_node_status_condition`) |
| Telemetry (fps / gpu / state) | **Prometheus** `eai_inference_*` series, remote_written by each nano's agent |
| History / trends | Grafana (eai-infra `metrics` role) reading central Prometheus |
| Media (video) | WebRTC, per nano |

The backend is a stateless read-through over central Prometheus: **no database, no heartbeat
ingest**. The frontend talks only to the backend (`/api/*`, proxied by `hooks.server.ts`).

## Data-flow standard — one gateway, read-only telemetry

```
 nano agents ──remote_write──▶ Prometheus ◀──read── fleet backend ◀──/api── browser
                                   ▲                                          (UI)
                                   └──read── Grafana  (separate; history only; <a href> only)
```

**The rule (don't deviate):**

1. **Browser → backend only.** The frontend calls `/api/fleet/*` and nothing else — never
   Prometheus or Grafana APIs. The "History" link is a plain `<a href>`, not a data call.
2. **The backend is the single Prometheus reader for the app** — **read-only instant queries**
   (`GET /api/v1/query`; no `remote_write`, no `query_range`/admin). It derives `FleetView` and owns
   the online/state rules. The only write the service makes anywhere is the k8s DaemonSet image PATCH.
3. **Grafana is a separate, independent read-only consumer** of the same Prometheus, for trends —
   not in the app's data path.

**Why:** same boundary rule as eai-nano/eai-catalog — *frontend → its own backend only; the backend
owns all infra access (Prometheus + k8s)*. One typed contract (Pydantic → generated TS), PromQL stays
server-side, and the write control (set-image) already needs a backend. The two surfaces split by
**capability** — live snapshot + controls = the app; history = Grafana — not duplication.

## API

- `GET /api/fleet/devices` → `FleetView`: per-device `health` (online/offline), `state`
  (running/stopped), `fps`, `gpu_utilization`, plus `total`/`online` counts.
- `POST /api/fleet/devices/{device_id}/inference/image` → set the inference container image
  (v1: fleet-wide behind a per-device shape — patches the `eai-nano-inference` DaemonSet).
- `GET /health`.

> The old `POST /api/fleet/heartbeat` ingest is **retired** (Spec 008).

## Layout

```
apps/
├── backend/                FastAPI (mirrors eai-nano apps/backend/app)
│   ├── app/
│   │   ├── main.py         create_app() — operationId = route.name (clean SDK names)
│   │   ├── config.py       Settings (env_prefix EAI_FLEET_)
│   │   ├── models.py       FleetView / DeviceView / Image* (strict Pydantic)
│   │   ├── prometheus.py   PrometheusClient + build_fleet_view (read-through)
│   │   ├── k8s.py          K8sClient (DaemonSet image PATCH; httpx2, in-cluster SA)
│   │   └── routers/        fleet.py + health.py
│   ├── tests/unit/         fake Prometheus + fake k8s; no Docker, no cluster
│   ├── pyproject.toml      console script `fleet-mgr` → app.main:run
│   └── Dockerfile
└── frontend/               SvelteKit + Carbon (mirrors eai-nano apps/frontend)
    ├── src/routes/         +layout.svelte (Header/SideNav/g90) + +page.svelte (fleet view)
    ├── src/lib/            hey-api.ts · errors.ts · state.svelte.ts · generated/fleet-backend-api/
    ├── src/hooks.server.ts proxies /api/* → EAI_FLEET_BACKEND_URL
    ├── scripts/gen-backend-api.mjs   `yarn gen:api` — dumps app.openapi() → @hey-api client
    └── Dockerfile          adapter-node (`node build`)
```

## Configure

Backend (env prefix `EAI_FLEET_`; injected by the eai-infra `eai-fleet` Ansible role):

| Var | Default | Meaning |
|-----|---------|---------|
| `EAI_FLEET_PROMETHEUS_URL` | `http://localhost:9090` | central Prometheus base URL |
| `EAI_FLEET_PROMETHEUS_TIMEOUT_S` | `5.0` | per-query timeout |
| `EAI_FLEET_PORT` | `8088` | HTTP port |
| `EAI_FLEET_KUBERNETES_API_URL` | `https://kubernetes.default.svc` | k3s API for the image-set route |
| `EAI_FLEET_INFERENCE_NAMESPACE` / `_DAEMONSET` / `_CONTAINER` | `eai-nano` / `eai-nano-inference` / `inference` | image-set target |

Frontend (`apps/frontend/.env.example`):

| Var | Meaning |
|-----|---------|
| `EAI_FLEET_BACKEND_URL` | **private** — where `hooks.server.ts` proxies `/api/*` (e.g. `http://<host>:8088`) |
| `EAI_FLEET_FRONTEND_GRAFANA_URL` | **public** — base for the per-device "History" link |

## Develop

Backend (fake Prometheus + fake k8s; no Docker, no cluster):

```bash
cd apps/backend
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"   # (.venv/bin on Linux)
pytest -q && ruff check . && pyright .
fleet-mgr                                  # serves on :8088
```

Frontend:

```bash
cd apps/frontend
yarn install
yarn gen:api            # regenerate the typed client from the live backend app.openapi()
yarn check              # svelte-check
cp .env.example .env    # point EAI_FLEET_BACKEND_URL at a running backend
yarn dev                # serves on :5173, proxies /api → backend
```

`make ci-lint ci-test ci-gen-types-check` from the repo root mirrors CI.

## Build & deploy

CI is `validate → build → deploy`. `make push` builds + pushes **two** config-free images
(`eai-fleet-backend`, `eai-fleet-frontend`); deploy triggers eai-infra's Ansible role
(`eai_infra/ansible/roles/eai-fleet/`). **eai-fleet builds; eai-infra deploys.**

Both images run as plain **Docker containers on the eai-infra host** (not k8s Pods, same
model as eai-catalog): the backend reaches the k3s API + Prometheus over the host IP, and
the frontend proxies `/api` to the backend **by container name over a shared docker
network** (`EAI_FLEET_BACKEND_URL`). The public `fleet.endoscopeai.com` ingress points at the
**frontend** container. See eai-nano `specs/008-jetson-nano-fleet/`.

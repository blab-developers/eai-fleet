# AGENTS.md — eai-fleet

Mandatory conventions for all agents working in this repository.

This file extends the canonical **[EAI Standards](../eai-nano/apps/backend/eai-core/docs/STANDARDIZATION.md)**
(in eai-core; vendored in sibling repos under `apps/backend/eai-core/docs/`). Rules below are
**fleet-specific** additions; they do not override the shared standard.

## Architecture — Stateless, Derived Fleet View (Spec 008)

- **No database.** Fleet state is derived at read time from central Prometheus.
  Online/offline comes from `kube_node_status_condition`; telemetry comes from the
  nano agents' `remote_write` series (`eai_inference_*`). There is no heartbeat
  ingest, no device registry table, no state persistence.
- **No Celery, no Redis, no task queue.** This is a read-only view + one mutating
  endpoint (image-set). Finalization, sync, and export are eai-catalog concerns.
- **`adapter-node` (not `adapter-static`).** The frontend runs as a Node server
  container and proxies `/api/*` via `hooks.server.ts` to the backend container.
  This is required because fleet-mgr deploys as a Docker container pair on
  eai-infra, not behind a shared ingress (unlike eai-nano which uses nginx).

## Demo mode — backend injects, frontend shows/hides (frontend calls the shots)

Demo mode lets the dashboard show canned devices when there are no real ones (sales/lab,
empty fleet). The split:
- **Backend (EXISTS):** `EAI_FLEET_DEMO_MODE` (a `Settings.demo_mode` bool, off in prod). When
  true AND the real derived fleet is empty, `GET /devices` injects canned `DeviceView`s — each
  marked **`demo=True`** (`app/demo.py` → `with_demo_when_empty`). Real Prometheus-derived
  devices are always `demo=False`. No demo data ever exists when the env is off.
- **Frontend (SHOWN):** a per-browser `demoMode` preference + a Settings toggle. The fleet store
  hides `demo=True` rows when the toggle is off (`applyDemoFilter` in `state.svelte.ts`). The
  frontend **does** filter here — *"frontend calls the shots"* (ADR-006).

**Why fleet filters on the client but eai-nano does NOT** (the cross-repo rule — do not "fix"
fleet to match nano, or vice-versa): nano's demo datum is an **actionable** clinical patient — a
hidden-but-present fake patient is still *recordable*, which is unsafe, so nano controls real
**existence** (create/delete via the normal patient API) and never client-filters. Fleet's demo
data is **inert, view-only** device rows (the fleet view is read-only/derived — nothing acts on a
row), so a client show/hide toggle is safe and correct. **Rule: client-side show/hide is fine for
inert view-data (fleet); actionable/stateful demo data controls real existence with no frontend
filter (nano).**

## Strong typing

- Same as EAI Universal: Pydantic strict (`extra="forbid"`), `StrEnum`, `pathlib.Path`.
- No SQLModel (no DB). No `dataclass`.
- `httpx2` only for outbound HTTP.

## Logging

- Follow the canonical EAI split: services initialize root logging with
  `eai.logging.setup_logging(...)`, CLIs/scripts use `eai.logging.setup_logger(...)` only when they
  need a named human-readable logger, and module loggers use `logging.getLogger(__name__)`.
- `eai.logging` owns the JSON/text schema and request-id behavior; fleet owns any file location.
  If the backend needs a persistent file, write under its app-local `.log/` directory and name it
  with env-var-level specificity, e.g. `eai_fleet_backend.log` or `eai_fleet_backend_access.log`.

## Frontend ↔ backend types

> **The cross-repo frontend standard lives in the canonical
> [EAI Standards → Frontend](../eai-nano/apps/backend/eai-core/docs/STANDARDIZATION.md).** Rules below
> are fleet-specific (note the `adapter-node` + `$env/dynamic` exception).

- Generate with `@hey-api/openapi-ts` → `src/lib/generated/fleet-backend-api/`.
- `hey-api.ts` resolves `baseUrl` as `env.EAI_FLEET_FRONTEND_API_BASE_URL ?? config?.baseUrl`
  (env-driven override, else the generated relative/same-origin default — no `''` literal). The
  browser always calls `/api/*` and `hooks.server.ts` proxies it to the backend container.
- **Runtime env via `$env/dynamic/public`** (not the universal `$env/static/public`) because
  `adapter-node` evaluates env at request time — this is the **one exception** to the universal
  rule. It is read where a value must be injected at deploy without a rebuild: the routes read
  `EAI_FLEET_FRONTEND_GRAFANA_URL` (History deep-links), and `hooks.server.ts` reads
  `EAI_FLEET_BACKEND_URL` from `$env/dynamic/private`.

## Backend ↔ external services — NO codegen

- **There is no backend↔service OpenAPI codegen.** The backend's outbound calls go to
  **Prometheus** (PromQL HTTP, `prometheus.py`) and the **Kubernetes API** (`k8s.py`) —
  neither is an OpenAPI service, so their responses are hand-parsed into strict Pydantic
  (`DeviceView`, `FleetView` in `models.py`). There is **no `datamodel-code-generator`** and
  **no generated Python client**; the only codegen in this repo is the frontend's hey-api TS
  client (above).
- **Contrast eai-nano:** nano's backend consumes the *inference* service's OpenAPI, so it
  generates Pydantic models with `datamodel-code-generator` + a hand-written `httpx2` client
  (`TODO(hey-api)` — interim until a real installable hey-api-for-Python ships, which would
  then generate both the models and the client from one spec, like the frontend). **That note
  does not apply here** — fleet has no such Python↔Python service boundary to generate from.

## Build / deploy

- **eai-fleet builds images; eai-infra deploys them — exactly like eai-catalog.** This repo
  contains **NO Ansible, Helm, or k3s/k8s manifests.** CI (`validate→build→deploy`) builds the
  two images, then the `deploy` job just triggers `cd …/eai-infra && make deploy-fleet-prod`;
  the eai-infra `eai-fleet` Ansible role injects vault secrets and runs the containers. (The
  one k8s touch in the code, `app/k8s.py`, is a runtime API *client* the backend uses to PATCH
  the inference DaemonSet image — an app feature, not deploy infra.)
- Config-free images; env/secrets injected at deploy by eai-infra Ansible+vault.
- **Config loading standard**: use Pydantic `BaseSettings`; precedence is `init > env vars > config.yaml > file secrets > defaults`. Env vars always win over the file. No `os.getenv()`, no `python-dotenv`.
- Corporate CA trust: `--build-context ca-trust=ca-trust/` — **backend image only** (pip
  behind the SSL-inspecting proxy). The frontend (`yarn`) image takes no CA context, same
  as eai-catalog. The Makefile applies `$(CA_TRUST)` to `ci-build-backend` only.
- **Frontend Carbon CSS / layout — see the canonical [EAI Standards → Frontend](../eai-nano/apps/backend/eai-core/docs/STANDARDIZATION.md).**
  In short: `vite.config.ts` keeps the `fixCarbonInvalidMediaQuery` transform plugin that rewrites
  Carbon v11's invalid `min-resolution >=` to the valid `resolution >=` form before minify (real fix,
  full minification, no warnings — **not** lightningcss `errorRecovery`, which ships invalid CSS).
  Layout uses Carbon CSS-Grid, not custom flexbox.

## Test infrastructure

- `tests/unit/` — **Vitest** (`*.test.ts`) on the SvelteKit vitest plugin + happy-dom, so
  imports resolve `$lib`/`$env` exactly like the app. Stateless service → no DB fixtures.
- No factories (no ORM models to build). Use fakes/mocks for Prometheus and K8s clients.
- E2E: **Playwright** (`*.spec.ts`) with API mocking (`page.route`) — the backend is
  stateless so real-process orchestration is not required.

## Style

- Same as EAI Universal: no `utils`/`helpers`/`misc`, public-before-private,
  `__init__.py` = docstring only.
- `install_deps.py` follows the canonical [EAI Standards → Install](../eai-nano/apps/backend/eai-core/docs/STANDARDIZATION.md):
  thin stdlib-only wrapper, `--dev`/`--dry-run`/`--check`/`--force`.

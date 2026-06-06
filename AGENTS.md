# AGENTS.md — eai-fleet

Mandatory conventions for all agents working in this repository.

This file extends the **EAI Universal Conventions** (see eai-core/docs/EAI-UNIVERSAL.md
or the eai-nano `AGENTS.md` Universal section). Rules below are **fleet-specific**
additions; they do not override the universal rules.

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

## Strong typing

- Same as EAI Universal: Pydantic strict (`extra="forbid"`), `StrEnum`, `pathlib.Path`.
- No SQLModel (no DB). No `dataclass`.
- `httpx2` only for outbound HTTP.

## Frontend ↔ backend types

- Generate with `@hey-api/openapi-ts` → `src/lib/generated/fleet-backend-api/`.
- `hey-api.ts` sets `baseUrl: ''` (same-origin): the browser always calls `/api/*` and
  `hooks.server.ts` proxies it to the backend container — so no client-visible backend URL
  is needed and there is no hand-written API wrapper.
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
- Corporate CA trust: `--build-context ca-trust=ca-trust/` — **backend image only** (pip
  behind the SSL-inspecting proxy). The frontend (`yarn`) image takes no CA context, same
  as eai-catalog. The Makefile applies `$(CA_TRUST)` to `ci-build-backend` only.
- **Frontend CSS minify — keep `css.lightningcss.errorRecovery: true` (load-bearing).**
  vite 8 made lightningcss the default CSS minifier (vitejs/vite#21911); it throws on
  Carbon v11's legacy `@media not all and (min-resolution >= 0.001dpcm)` hack. esbuild
  isn't an option — SvelteKit forces `cssMinify = !!build.minify` and its config wins, so
  `build.cssMinify: 'esbuild'` is ignored. `errorRecovery` downgrades the parse error to a
  warning so CSS **and** JS still fully minify. Do **not** "fix" it with `build.minify:false`.
- **Layout uses Carbon CSS-Grid** (`Grid`/`Row`/`Column`) for page columns — not custom
  flexbox containers.

## Test infrastructure

- `tests/unit/` — **Vitest** (`*.test.ts`) on the SvelteKit vitest plugin + happy-dom, so
  imports resolve `$lib`/`$env` exactly like the app. Stateless service → no DB fixtures.
- No factories (no ORM models to build). Use fakes/mocks for Prometheus and K8s clients.
- E2E: **Playwright** (`*.spec.ts`) with API mocking (`page.route`) — the backend is
  stateless so real-process orchestration is not required.

## Style

- Same as EAI Universal: no `utils`/`helpers`/`misc`, public-before-private,
  `__init__.py` = docstring only.
- `install_deps.py` follows the EAI Install Standard (see eai-nano
  `docs/EAI-INSTALL-STANDARD.md`): thin wrapper, `--dev`/`--dry-run`/`--check`/`--force`.

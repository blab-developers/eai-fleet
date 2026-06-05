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
- `hey-api.ts` uses `$env/dynamic/public` (runtime env) because `adapter-node`
  evaluates env at request time. This is the **one exception** to the universal
  `$env/static/public` rule — document it here.
- No hand-written API wrapper.

## Build / deploy

- Config-free images; env/secrets injected at deploy by eai-infra Ansible+vault.
- Corporate CA trust: `--build-context ca-trust=ca-trust/` in Docker builds.
- No Helm — plain containers managed by Ansible (same as eai-nano).

## Test infrastructure

- `tests/unit/` only (stateless service; no DB fixtures needed).
- No factories (no ORM models to build). Use fakes/mocks for Prometheus and K8s clients.
- E2E: Playwright with API mocking (`page.route`) — the backend is stateless so
  real-process orchestration is not required.

## Style

- Same as EAI Universal: no `utils`/`helpers`/`misc`, public-before-private,
  `__init__.py` = docstring only.
- `install_deps.py` follows the EAI Install Standard (see eai-nano
  `docs/EAI-INSTALL-STANDARD.md`): thin wrapper, `--dev`/`--dry-run`/`--check`/`--force`.

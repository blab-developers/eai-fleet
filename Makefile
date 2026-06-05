# eai-fleet — `make ci-*` is the source of truth for what CI runs.
#
# Two images now (apps/backend + apps/frontend), mirroring eai-nano / eai-catalog:
#   - eai-fleet-backend : FastAPI fleet-view API (derives state from Prometheus; patches DS)
#   - eai-fleet-frontend: SvelteKit live fleet UI (accordion per device + set-image control)
# Both deploy as plain Docker containers on the eai-infra host (NOT k8s Pods); see
# eai-infra ansible/roles/eai-fleet.

# Default to the in-cluster registry NodePort so local builds + ansible's image pull
# see the same URL. CI overrides REGISTRY to the public DNS name when pushing.
REGISTRY ?= localhost:30500
GIT_SHA  ?= $(shell git rev-parse HEAD 2>/dev/null || echo unknown)
CA_TRUST := --build-context ca-trust=ca-trust/
# Image names match what eai-infra's eai-fleet role pulls. Keep them in sync.
BACKEND_IMAGE  := $(REGISTRY)/eai-fleet-backend
FRONTEND_IMAGE := $(REGISTRY)/eai-fleet-frontend

BACKEND_DIR  := apps/backend
FRONTEND_DIR := apps/frontend

.PHONY: help dev-backend dev-frontend lint test \
        ci-lint ci-lint-backend ci-lint-frontend \
        ci-test ci-test-backend ci-test-frontend ci-gen-types-check \
        ci-build ci-build-backend ci-build-frontend push

help: ## Show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ -/'

dev-backend: ## Run the backend (uvicorn) on :8088
	cd $(BACKEND_DIR) && fleet-mgr

dev-frontend: ## Run the frontend (vite dev) on :5173
	cd $(FRONTEND_DIR) && yarn dev

lint: ci-lint
test: ci-test

# ── CI source of truth ──────────────────────────────────────────────────────

ci-lint: ci-lint-backend ci-lint-frontend ## lint both apps

ci-lint-backend: ## ruff + pyright (backend)
	cd $(BACKEND_DIR) && ruff check . && ruff format --check . && pyright .

ci-lint-frontend: ## svelte-check (frontend)
	cd $(FRONTEND_DIR) && yarn check

ci-test: ci-test-backend ci-test-frontend ## test both apps

ci-test-backend: ## pytest (fake Prometheus + fake k8s; no Docker, no cluster)
	cd $(BACKEND_DIR) && pytest -q --timeout=60

ci-test-frontend: ## playwright e2e (mocks /api in-browser; needs a chromium install)
	cd $(FRONTEND_DIR) && yarn test:e2e

ci-gen-types-check: ## regenerate the API client and fail on drift
	cd $(FRONTEND_DIR) && yarn gen:api
	git diff --exit-code $(FRONTEND_DIR)/src/lib/generated/ \
		|| (echo "ERROR: generated API client is stale — run 'yarn gen:api' in apps/frontend" && exit 1)

ci-build: ci-build-backend ci-build-frontend ## build both images

ci-build-backend: ## build + tag the backend image
	-docker pull $(BACKEND_IMAGE):latest
	docker build $(CA_TRUST) \
		--cache-from $(BACKEND_IMAGE):latest \
		--build-arg BUILDKIT_INLINE_CACHE=1 \
		-t $(BACKEND_IMAGE):$(GIT_SHA) \
		-t $(BACKEND_IMAGE):latest \
		$(BACKEND_DIR)

ci-build-frontend: ## build + tag the frontend image
	-docker pull $(FRONTEND_IMAGE):latest
	docker build \
		--cache-from $(FRONTEND_IMAGE):latest \
		--build-arg BUILDKIT_INLINE_CACHE=1 \
		--build-arg GIT_SHA=$(GIT_SHA) \
		-t $(FRONTEND_IMAGE):$(GIT_SHA) \
		-t $(FRONTEND_IMAGE):latest \
		$(FRONTEND_DIR)

push: ci-build ## build + push both images (:$(GIT_SHA) and :latest)
	docker push $(BACKEND_IMAGE):$(GIT_SHA)
	docker push $(BACKEND_IMAGE):latest
	docker push $(FRONTEND_IMAGE):$(GIT_SHA)
	docker push $(FRONTEND_IMAGE):latest

# eai-fleet — Development Commands
#
# Standard interface per eai-nano ADR-007:
#   make install          # install backend + frontend deps
#   make dev              # run backend + frontend locally
#   make dev-backend      # run backend (uvicorn) on :8088
#   make dev-frontend     # run frontend (vite dev) on :5176
#   make test             # run backend + frontend tests
#   make lint             # run backend + frontend linters
#   make build            # build backend + frontend images
#   make push             # build + push images

.PHONY: help install dev dev-backend dev-frontend \
        test test-backend test-frontend lint lint-backend lint-frontend \
        build build-backend build-frontend push gen-types-check

REGISTRY ?= localhost:30500
GIT_SHA  ?= $(shell git rev-parse HEAD 2>/dev/null || echo unknown)
CA_TRUST := --build-context ca-trust=ca-trust/
BACKEND_IMAGE  := $(REGISTRY)/eai-fleet-backend
FRONTEND_IMAGE := $(REGISTRY)/eai-fleet-frontend
BACKEND_DIR  := apps/backend
FRONTEND_DIR := apps/frontend

# Detect the backend venv interpreter (Windows Git Bash vs Unix).
define backend_python
$(shell test -f $(BACKEND_DIR)/.venv/Scripts/python.exe && echo $(BACKEND_DIR)/.venv/Scripts/python.exe || echo $(BACKEND_DIR)/.venv/bin/python)
endef

help: ## Show available targets
	@echo "EAI-Fleet — Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# Install
# =============================================================================

install: ## Install backend + frontend deps
	cd $(BACKEND_DIR) && $(call backend_python) -m pip install -e ".[dev]"
	cd $(FRONTEND_DIR) && yarn install

# =============================================================================
# Development
# =============================================================================

dev: ## Run backend + frontend locally (run `make dev-backend` and `make dev-frontend` in separate terminals)
	@echo "Run these in separate terminals:"
	@echo "  make dev-backend"
	@echo "  make dev-frontend"

dev-backend: ## Run the backend (uvicorn) on :8088
	cd $(BACKEND_DIR) && $(call backend_python) -m fleet_mgr

dev-frontend: ## Run the frontend (vite dev) on :5176
	cd $(FRONTEND_DIR) && yarn dev

# =============================================================================
# Testing & Quality
# =============================================================================

test: test-backend test-frontend ## Run backend + frontend tests

test-backend: ## Run backend tests (fake Prometheus + fake k8s; no Docker, no cluster)
	cd $(BACKEND_DIR) && $(call backend_python) -m pytest -q --timeout=60

test-frontend: ## Run Playwright E2E tests (mocks /api in-browser)
	cd $(FRONTEND_DIR) && yarn test:e2e

lint: lint-backend lint-frontend ## Run backend + frontend linters + Makefile check

lint-backend: ## ruff + pyright (backend)
	$(call backend_python) scripts/check_makefile.py Makefile
	cd $(BACKEND_DIR) && ruff check . && ruff format --check . && $(call backend_python) -m pyright .

lint-frontend: ## svelte-check (frontend)
	cd $(FRONTEND_DIR) && yarn check

# =============================================================================
# Generated types
# =============================================================================

gen-types-check: ## Regenerate the API client and fail on drift
	cd $(FRONTEND_DIR) && yarn gen:api
	git diff --exit-code $(FRONTEND_DIR)/src/lib/generated/ \
		|| (echo "ERROR: generated API client is stale — run 'yarn gen:api' in apps/frontend" && exit 1)

# =============================================================================
# Build & Push
# =============================================================================

build: build-backend build-frontend ## Build backend + frontend images

build-backend: ## Build the backend image
	-docker pull $(BACKEND_IMAGE):latest
	docker build $(CA_TRUST) \
		--cache-from $(BACKEND_IMAGE):latest \
		--build-arg BUILDKIT_INLINE_CACHE=1 \
		-t $(BACKEND_IMAGE):$(GIT_SHA) \
		-t $(BACKEND_IMAGE):latest \
		$(BACKEND_DIR)

build-frontend: ## Build the frontend image
	-docker pull $(FRONTEND_IMAGE):latest
	docker build \
		--cache-from $(FRONTEND_IMAGE):latest \
		--build-arg BUILDKIT_INLINE_CACHE=1 \
		--build-arg GIT_SHA=$(GIT_SHA) \
		-t $(FRONTEND_IMAGE):$(GIT_SHA) \
		-t $(FRONTEND_IMAGE):latest \
		$(FRONTEND_DIR)

push: build ## Build and push both images (:$(GIT_SHA) and :latest)
	docker push $(BACKEND_IMAGE):$(GIT_SHA)
	docker push $(BACKEND_IMAGE):latest
	docker push $(FRONTEND_IMAGE):$(GIT_SHA)
	docker push $(FRONTEND_IMAGE):latest

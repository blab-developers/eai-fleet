# fleet-mgr — `make ci-*` is the source of truth for what root Makefile runs.

REGISTRY ?= registry.endoscopeai.com
GIT_SHA  ?= $(shell git rev-parse HEAD 2>/dev/null || echo unknown)
CA_TRUST := --build-context ca-trust=ca-trust/
IMAGE    := $(REGISTRY)/eai-nano/fleet-mgr

.PHONY: help dev lint test ci-lint ci-test ci-build

help: ## Show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ -/'

dev: ## Run locally
	fleet-mgr

lint: ci-lint
test: ci-test

# ── CI source of truth ──────────────────────────────────────────────────────

ci-lint: ## ruff + pyright
	ruff check .
	ruff format --check .
	pyright .

ci-test: ## pytest (fake Prometheus; no Docker, no cluster)
	pytest -q --timeout=60

ci-build: ## build + tag the config-free image
	-docker pull $(IMAGE):latest
	docker build \
		--cache-from $(IMAGE):latest \
		--build-arg BUILDKIT_INLINE_CACHE=1 \
		$(CA_TRUST) \
		-t $(IMAGE):$(GIT_SHA) \
		-t $(IMAGE):latest \
		.

# fleet-mgr — `make ci-*` is the source of truth for what root Makefile runs.

# Default to the in-cluster registry NodePort so local builds + ansible's
# image pull see the same URL. CI overrides REGISTRY to the public DNS name
# (registry.endoscopeai.com) when pushing from the GitLab runner.
REGISTRY ?= localhost:30500
GIT_SHA  ?= $(shell git rev-parse HEAD 2>/dev/null || echo unknown)
# Image name matches what eai-infra's eai-fleet role pulls. Keep them in sync.
IMAGE    := $(REGISTRY)/eai-fleet

.PHONY: help dev lint test ci-lint ci-test ci-build push

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
		-t $(IMAGE):$(GIT_SHA) \
		-t $(IMAGE):latest \
		.

push: ci-build ## build + push :$(GIT_SHA) and :latest
	docker push $(IMAGE):$(GIT_SHA)
	docker push $(IMAGE):latest

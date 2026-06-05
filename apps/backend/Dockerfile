# syntax=docker/dockerfile:1.7
# fleet-mgr backend — config-free image (env/secrets injected at deploy by eai-infra).
# Multi-stage: deps cached on pyproject alone; runtime carries venv + the app package.

FROM python:3.12-slim AS deps
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install .

FROM python:3.12-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
# UID/GID 999 matches the SA-credential file ownership the eai-infra role writes
# on the host (see roles/eai-fleet/tasks/main.yml) so the bind-mounted token is readable.
RUN groupadd -r -g 999 app && useradd -r -u 999 -g app app
COPY --from=deps /opt/venv /opt/venv
COPY --chown=app:app app ./app
USER app
EXPOSE 8088
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8088/health || exit 1
CMD ["fleet-mgr"]

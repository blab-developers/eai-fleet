# ca-trust/

Corporate CA bundle for builds behind SSL-inspecting proxies (OchsnerCA), mirroring
the `eai-catalog` / `eai-mlops` convention. `ca-bundle.crt` holds the real corporate
root CA(s) and is committed on purpose — a CA *certificate* is public (not a private
key) — so local builds behind the proxy and CI builds work the same way.

## How it's consumed

The bundle is passed to each image build as a **named build context** and installed
into the image's system trust store:

```
# Makefile (CI source of truth) and `make build`:
CA_TRUST := --build-context ca-trust=ca-trust/
docker build $(CA_TRUST) ... apps/<service>/

# docker-compose.yml (local):
build:
  context: ./apps/<service>
  additional_contexts:
    ca-trust: ./ca-trust/
```

`--build-context` (CLI) and `additional_contexts` (compose) are the same BuildKit
feature. A named context is used because the cert lives here at repo root, outside
each service's `apps/<service>` build context.

Each apt-based Dockerfile (backend, inference, inference dev, chromium — **not** the
Alpine frontend) then does, before any apt/pip step that needs TLS:

```dockerfile
COPY --from=ca-trust ca-bundle.crt /usr/local/share/ca-certificates/corporate.crt
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && csplit -s -z /usr/local/share/ca-certificates/corporate.crt '/-----BEGIN CERTIFICATE-----/' '{*}' -f /usr/local/share/ca-certificates/corp_ \
    && for f in /usr/local/share/ca-certificates/corp_*; do mv "$f" "$f.crt"; done \
    && rm /usr/local/share/ca-certificates/corporate.crt \
    && update-ca-certificates
```

`csplit` splits the multi-cert bundle into one cert per file, because
`update-ca-certificates` expects that.

## Local Git (not Docker)

For `git` TLS behind the proxy, don't disable verification — trust the Windows store
instead: run `scripts/fix_git_tls_trust.ps1` (sets `http.sslBackend=schannel`).

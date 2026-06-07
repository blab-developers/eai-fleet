"""Corporate CA-trust block — duplication is fine, drift is not.

The canonical block lives in eai-core (`docs/ca-trust.dockerfile`); every apt-based image
across the EAI repos inlines it byte-for-byte (no shared base image — the apps have
different bases). eai-fleet does not vendor eai-core, so we pin the canonical text here and
assert the backend Dockerfile carries it verbatim. Keep this constant in sync with
eai-core's `docs/ca-trust.dockerfile` (the cross-repo source of truth).
"""

# ruff: noqa: E501 — the canonical block below must be verbatim; its lines exceed 100 by design.

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]

# Byte-for-byte copy of eai-core/docs/ca-trust.dockerfile (the cross-repo canonical).
CANONICAL = """\
COPY --from=ca-trust ca-bundle.crt /usr/local/share/ca-certificates/corporate.crt
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \\
    && csplit -s -z /usr/local/share/ca-certificates/corporate.crt '/-----BEGIN CERTIFICATE-----/' '{*}' -f /usr/local/share/ca-certificates/corp_ \\
    && for f in /usr/local/share/ca-certificates/corp_*; do mv "$f" "$f.crt"; done \\
    && rm /usr/local/share/ca-certificates/corporate.crt \\
    && update-ca-certificates"""


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n")


def test_backend_dockerfile_has_canonical_ca_trust_block() -> None:
    """The apt-based backend image inlines the eai-core canonical CA-trust block verbatim."""
    body = _norm((REPO_ROOT / "apps" / "backend" / "Dockerfile").read_text(encoding="utf-8"))
    assert CANONICAL in body, (
        "backend Dockerfile CA-trust block drifted from the eai-core canonical "
        "(eai-core/docs/ca-trust.dockerfile). Copy it back byte-for-byte."
    )


def test_frontend_has_no_ca_trust_block() -> None:
    """Frontend is alpine/node (no corporate-CA apt install) — it must NOT carry the block."""
    fe = REPO_ROOT / "apps" / "frontend" / "Dockerfile"
    assert "update-ca-certificates" not in _norm(fe.read_text(encoding="utf-8"))

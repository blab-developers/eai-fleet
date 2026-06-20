"""Config from environment (12-factor; same image everywhere)."""

from pathlib import Path

from eai.contracts import CACHE_DIR
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Fleet-manager settings.

    fleet-mgr holds **no** device state for the read side (Spec 008): the fleet view
    is derived from central Prometheus — online/offline from KubeEdge node status
    (kube-state-metrics) and telemetry from the nano agents' remote_written
    ``eai_inference_*`` series.

    The image-set endpoint (``POST /api/fleet/devices/{id}/inference/image``) is the
    one mutating route. It strategic-merge-patches the inference DaemonSet in the
    central k3s, reaching the API via the standard in-cluster auth files mounted
    by the eai-infra ansible role. v1 is fleet-wide (the patch hits every Nano
    that matches the DaemonSet's nodeSelector) — see the route docstring.
    """

    # env_prefix="EAI_FLEET_" namespaces every field-derived env var to this
    # service so it can't collide with another EAI_* app on the same host (e.g.
    # eai-mlops also exports EAI_PROMETHEUS_URL). Fields stay short
    # (settings.prometheus_url, settings.port, …); the deployer exports
    # EAI_FLEET_PROMETHEUS_URL, EAI_FLEET_PORT, etc. case_sensitive=False keeps
    # the read tolerant.
    model_config = SettingsConfigDict(case_sensitive=False, env_prefix="EAI_FLEET_")

    prometheus_url: str = "http://localhost:9090"
    prometheus_timeout_s: float = 5.0
    port: int = 8088
    log_level: str = "INFO"

    # Demo mode (EAI_FLEET_DEMO_MODE): when true AND the real derived fleet is empty, GET /devices
    # injects canned demo devices (marked demo=True). Off in production. The frontend's per-browser
    # toggle decides whether to SHOW them — "frontend calls the shots" (ADR-006); the device rows
    # are inert/view-only, so client-side hide/show is safe (unlike nano's recordable patient).
    demo_mode: bool = False

    # --- Model package deployment ---
    # eai-catalog is the source of truth; fleet caches packages using the shared
    # eai-core cache root before pushing them to nano backends.
    catalog_url: str = "http://localhost:8000/api/v1"
    catalog_token: str = ""
    model_cache_dir: Path = CACHE_DIR / "models"
    model_deploy_timeout_s: float = 60.0

    # --- Recordings replication (RecordingsPuller) ---
    # Destination for pulled nano recordings (mp4 + ndjson sidecar). In prod this
    # is the shared NFS mount the eai-catalog device-prediction ingest reads
    # (EAI_FLEET_RECORDINGS_DIR=/mnt/eai/eai-backups/eai-nano). The per-device
    # nano base_url + bearer token are caller-supplied per pull (like model deploy),
    # since fleet has no device→URL map (Spec 008: stateless, no device state).
    recordings_dir: Path = CACHE_DIR / "recordings"
    recordings_pull_timeout_s: float = 30.0
    recordings_pull_page_size: int = 100

    # --- Kubernetes (image-set endpoint) ---
    # Defaults match the canonical in-cluster SA mount. The eai-infra role drops
    # a token + the k3s CA at these paths for the docker container (not a Pod).
    kubernetes_api_url: str = "https://kubernetes.default.svc"
    kubernetes_token_path: Path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
    kubernetes_ca_path: Path = Path("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
    kubernetes_timeout_s: float = 10.0

    # The DaemonSet the image-set endpoint targets. Defaults match
    # eai-nano/deploy/10-inference.yaml. Override per environment if the manifest
    # ever splits or renames.
    inference_namespace: str = "eai-nano"
    inference_daemonset: str = "eai-nano-inference"
    inference_container: str = "inference"


settings = Settings()

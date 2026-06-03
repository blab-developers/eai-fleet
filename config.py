"""Config from environment (12-factor; same image everywhere)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Fleet-manager settings.

    fleet-mgr holds **no** device state (Spec 008): it derives the fleet view by
    reading central Prometheus — online/offline from KubeEdge node status
    (kube-state-metrics) and telemetry from the nano agents' remote_written
    ``eai_inference_*`` series. So there is no database and no offline timer; the
    one thing it needs is where central Prometheus lives.
    """

    # env_prefix="EAI_" puts every field-derived env var under the project's
    # namespace. Field names stay short (settings.prometheus_url, settings.
    # fleet_port, …) but the deployer must export EAI_PROMETHEUS_URL,
    # EAI_FLEET_PORT, etc. case_sensitive=False keeps the read tolerant.
    model_config = SettingsConfigDict(case_sensitive=False, env_prefix="EAI_")

    prometheus_url: str = "http://localhost:9090"
    prometheus_timeout_s: float = 5.0
    fleet_port: int = 8088
    log_level: str = "INFO"


settings = Settings()

"""Config from environment (12-factor; same image everywhere)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Fleet-manager settings. Postgres in prod; SQLite dev default."""

    model_config = SettingsConfigDict(case_sensitive=False)

    database_url: str = "sqlite:///nano_fleet.db"
    offline_after_s: int = 30
    fleet_port: int = 8088
    log_level: str = "INFO"


settings = Settings()

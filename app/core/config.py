from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "fastapi-scada-odoo"
    environment: str = "development"
    log_level: str = "info"

    database_url: str = Field(..., validation_alias="DATABASE_URL")

    # PLC Connection Settings
    plc_ip: str = Field(default="192.168.1.2", validation_alias="PLC_IP")
    plc_port: int = Field(default=9600, validation_alias="PLC_PORT")
    plc_protocol: str = Field(default="udp", validation_alias="PLC_PROTOCOL")
    plc_timeout_sec: float = Field(default=2.0, validation_alias="PLC_TIMEOUT_SEC")
    client_node: int = Field(default=1, validation_alias="CLIENT_NODE")
    plc_node: int = Field(default=2, validation_alias="PLC_NODE")

    plc_read_map: str = "{}"
    plc_write_map: str = "{}"

    odoo_base_url: str = Field(..., validation_alias="ODOO_BASE_URL")
    odoo_url: str = Field(..., validation_alias="ODOO_URL")
    odoo_db: str = Field(..., validation_alias="ODOO_DB")
    odoo_username: str = Field(..., validation_alias="ODOO_USERNAME")
    odoo_password: str = Field(..., validation_alias="ODOO_PASSWORD")

    # Auto-sync settings
    enable_auto_sync: bool = Field(default=False, validation_alias="ENABLE_AUTO_SYNC")
    sync_interval_minutes: int = Field(default=5, validation_alias="SYNC_INTERVAL_MINUTES")
    sync_batch_limit: int = Field(default=10, validation_alias="SYNC_BATCH_LIMIT")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

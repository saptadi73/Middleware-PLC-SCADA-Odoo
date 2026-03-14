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
    cors_allow_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080",
        validation_alias="CORS_ALLOW_ORIGINS",
    )
    cors_allow_methods: str = Field(default="*", validation_alias="CORS_ALLOW_METHODS")
    cors_allow_headers: str = Field(default="*", validation_alias="CORS_ALLOW_HEADERS")
    cors_allow_credentials: bool = Field(default=True, validation_alias="CORS_ALLOW_CREDENTIALS")

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

    # Scheduler Master Control
    enable_auto_sync: bool = Field(default=False, validation_alias="ENABLE_AUTO_SYNC")
    
    # Scheduler: Individual Task Control
    enable_task_1_auto_sync: bool = Field(default=True, validation_alias="ENABLE_TASK_1_AUTO_SYNC")
    enable_task_2_plc_read: bool = Field(default=True, validation_alias="ENABLE_TASK_2_PLC_READ")
    enable_task_3_process_completed: bool = Field(default=True, validation_alias="ENABLE_TASK_3_PROCESS_COMPLETED")
    enable_task_4_health_monitor: bool = Field(default=True, validation_alias="ENABLE_TASK_4_HEALTH_MONITOR")
    enable_task_5_equipment_failure: bool = Field(default=True, validation_alias="ENABLE_TASK_5_EQUIPMENT_FAILURE")
    enable_task_6_log_cleanup: bool = Field(default=True, validation_alias="ENABLE_TASK_6_LOG_CLEANUP")
    
    # Auto-sync settings
    sync_interval_minutes: int = Field(default=60, validation_alias="SYNC_INTERVAL_MINUTES")
    sync_batch_limit: int = Field(default=10, validation_alias="SYNC_BATCH_LIMIT")
    plc_read_interval_minutes: int = Field(default=5, validation_alias="PLC_READ_INTERVAL_MINUTES")
    process_completed_interval_minutes: int = Field(default=3, validation_alias="PROCESS_COMPLETED_INTERVAL_MINUTES")
    health_monitor_interval_minutes: int = Field(default=10, validation_alias="HEALTH_MONITOR_INTERVAL_MINUTES")
    batch_stuck_threshold_minutes: int = Field(default=15, validation_alias="BATCH_STUCK_THRESHOLD_MINUTES")
    equipment_failure_interval_minutes: int = Field(default=5, validation_alias="EQUIPMENT_FAILURE_INTERVAL_MINUTES")
    log_cleanup_interval_minutes: int = Field(default=1440, validation_alias="LOG_CLEANUP_INTERVAL_MINUTES")
    log_retention_days: int = Field(default=30, validation_alias="LOG_RETENTION_DAYS")
    log_cleanup_keep_last: int = Field(default=1000, validation_alias="LOG_CLEANUP_KEEP_LAST")

    # Batch capacity sanity warning thresholds (kg)
    expected_batch_max_kg: float = Field(default=1000.0, validation_alias="EXPECTED_BATCH_MAX_KG")
    batch_weight_warn_margin_kg: float = Field(default=50.0, validation_alias="BATCH_WEIGHT_WARN_MARGIN_KG")

    @staticmethod
    def _split_csv(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        origins = self._split_csv(self.cors_allow_origins)
        return origins or ["*"]

    @property
    def cors_methods_list(self) -> list[str]:
        methods = self._split_csv(self.cors_allow_methods)
        return methods or ["*"]

    @property
    def cors_headers_list(self) -> list[str]:
        headers = self._split_csv(self.cors_allow_headers)
        return headers or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

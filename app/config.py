from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/events"
    app_name: str = "event-ingestion-api"
    debug: bool = False
    log_level: str = "INFO"
    ingest_rate_limit: str = "100/minute"
    bulk_rate_limit: str = "20/minute"
    list_rate_limit: str = "200/minute"
    get_rate_limit: str = "300/minute"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

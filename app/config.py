from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Jordan Tender Assistant"
    version: str = "0.5.0"
    api_prefix: str = "/api/v1"
    max_upload_mb: int = 25

    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    llm_timeout_seconds: float = 60.0

    ocr_enabled: bool = True

    # SQLite keeps local runs simple; Docker Compose points this at Postgres.
    database_url: str = "sqlite:///./tender_assistant.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_eager: bool = False


settings = Settings()

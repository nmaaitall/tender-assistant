from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Jordan Tender Assistant"
    version: str = "0.3.0"
    api_prefix: str = "/api/v1"
    max_upload_mb: int = 25

    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    llm_timeout_seconds: float = 60.0


settings = Settings()

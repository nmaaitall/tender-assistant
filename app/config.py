from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Jordan Tender Assistant"
    version: str = "0.7.0"
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

    # Without QDRANT_URL passages are stored in a local folder, which only one
    # process can open: run jobs with CELERY_EAGER=true, or use the Qdrant server.
    qdrant_url: str | None = None
    qdrant_path: str = "./qdrant_data"
    # An empty model name turns that stage off (lexical search only, no reranking).
    embedding_model: str = "google/embeddinggemma-300m"
    reranker_model: str = "BAAI/bge-reranker-v2-m3-int8"
    model_cache_dir: str | None = None


settings = Settings()

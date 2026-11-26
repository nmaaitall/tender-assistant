from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Jordan Tender Assistant"
    version: str = "0.2.0"
    api_prefix: str = "/api/v1"
    max_upload_mb: int = 25


settings = Settings()

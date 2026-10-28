from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_secret: str = Field(min_length=32)  # HS256 key; short secrets are brute-forceable
    jwt_expiry_hours: int = 8
    cookie_secure: bool = True
    database_url: str = "sqlite:///./app.db"
    storage_dir: Path = Path("./storage")
    frontend_origin: str = "http://localhost:5173"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_chat_model: str = ""
    llm_image_model: str = ""
    llm_image_size: str = "1024x1536"
    llm_image_quality: str = "medium"
    ai_mock: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()

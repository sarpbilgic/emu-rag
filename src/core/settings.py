from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    qdrant_url: str
    qdrant_api_key: str
    xai_api_key: str
    voyage_api_key: str
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    return settings

settings = get_settings()
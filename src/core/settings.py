from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache, cached_property
from typing import Optional

class Settings(BaseSettings):
    qdrant_url: str
    qdrant_api_key: str
    xai_api_key: str
    voyage_api_key: str
    database_url: str
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    @cached_property
    def async_database_url(self) -> str:
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://")

@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    return settings



settings = get_settings()
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache, cached_property
from typing import Optional

class Settings(BaseSettings):
    qdrant_url: str
    qdrant_api_key: str
    xai_api_key: str
    database_url: str
    redis_url: str
    algorithm: str
    secret_key: str
    access_token_expire_minutes: int = 60 * 24
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    @cached_property
    def async_database_url(self) -> str:
        url = self.database_url.replace("postgresql://", "postgresql+asyncpg://")
        if "?" in url:
            base_url, params = url.split("?", 1)
            param_pairs = [p for p in params.split("&") if not p.startswith(("sslmode=", "channel_binding="))]
            if param_pairs:
                url = f"{base_url}?{'&'.join(param_pairs)}"
            else:
                url = base_url
        return url

@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    return settings

settings = get_settings()
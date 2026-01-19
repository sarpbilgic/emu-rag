from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache, cached_property
from typing import Optional

class Settings(BaseSettings):
    env : str
    qdrant_url: str
    qdrant_api_key: str
    xai_api_key: str
    database_url: str
    redis_url: str
    algorithm: str
    secret_key: str
    access_token_expire_minutes: int = 60 * 24
    microsoft_client_id: str
    microsoft_client_secret: str
    microsoft_tenant_id: str
    tavily_api_key: str
    api_base_url: str
    anonymous_chat_ttl: int = 86400
    authenticated_chat_ttl: Optional[int] = None

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

    @cached_property
    def microsoft_redirect_uri(self) -> str:
        return f"{self.api_base_url}/api/v1/auth/microsoft/callback"

@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    return settings

settings = get_settings()

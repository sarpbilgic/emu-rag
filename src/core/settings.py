from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
    gemini_api_key: str
    xai_api_key: str
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8"     
    )

@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    return settings

settings = get_settings()
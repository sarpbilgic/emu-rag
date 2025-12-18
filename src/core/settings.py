from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    # Optional: Qdrant (can test without it)
    qdrant_url: Optional[str] = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    
    # Required: API keys for LLM and Embeddings
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
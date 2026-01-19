"""
AdsGen 2.0 - Configuration Module
Centralized configuration using Pydantic Settings
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql+asyncpg://adsgen:adsgen_secret@localhost:5432/adsgen"
    
    # Redis (Celery broker)
    redis_url: str = "redis://localhost:6379/0"
    
    # AI Services
    deepseek_api_key: str = ""
    deepseek_api_url: str = "https://api.deepseek.com/v1/chat/completions"
    deepseek_model: str = "deepseek-chat"
    
    # ComfyUI (Image Generation)
    comfyui_url: str = "http://localhost:8188"
    
    # Yandex Disk
    yandex_disk_token: str = ""
    yandex_disk_folder: str = "Картинки_Авито"
    
    # Google Sheets
    google_credentials_json: str = ""
    
    # Avito API
    avito_client_id: str = ""
    avito_client_secret: str = ""
    
    # Application
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

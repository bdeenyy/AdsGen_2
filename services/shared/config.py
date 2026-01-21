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
    
    # CORS (comma-separated list of allowed origins, or "*" for all)
    cors_origins: str = "http://localhost:3000,http://localhost:8000"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# ═══════════════════════════════════════════════════════════════════════════
# STEP MODE CONTROL (stored in Redis for dynamic updates)
# ═══════════════════════════════════════════════════════════════════════════

_STEP_MODE_KEY = "adsgen:step_mode"


def is_step_mode_enabled() -> bool:
    """
    Check if step mode is enabled.
    In step mode, workers don't automatically trigger the next worker.
    """
    import redis
    try:
        r = redis.from_url(get_settings().redis_url)
        value = r.get(_STEP_MODE_KEY)
        return value == b"1" or value == b"true"
    except Exception:
        return False  # Default to auto mode if Redis unavailable


def set_step_mode(enabled: bool) -> bool:
    """Enable or disable step mode."""
    import redis
    try:
        r = redis.from_url(get_settings().redis_url)
        r.set(_STEP_MODE_KEY, "1" if enabled else "0")
        return True
    except Exception:
        return False


def get_step_mode() -> bool:
    """Get current step mode status."""
    return is_step_mode_enabled()

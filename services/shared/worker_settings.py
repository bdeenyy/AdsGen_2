"""
AdsGen 2.0 - Worker Settings Module
Dynamic worker settings stored in Redis for real-time updates without restart
"""

import json
import logging
from typing import Any, Dict, Optional

import redis

from services.shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Redis key prefix for worker settings
WORKER_SETTINGS_PREFIX = "adsgen:worker_settings:"


# ═══════════════════════════════════════════════════════════════════════════
# DEFAULT SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_SETTINGS = {
    "textgen": {
        "name": "TextGen Worker",
        "icon": "📝",
        "description": "Генерация заголовков и описаний вакансий",
        "settings": {
            "ai_provider": {
                "label": "AI Провайдер",
                "type": "select",
                "options": ["deepseek", "polza", "local"],
                "default": "deepseek",
            },
            "polza_api_key": {
                "label": "Polza.ai API Key",
                "type": "text",
                "default": "",
                "placeholder": "sk-...",
                "show_when": {"ai_provider": "polza"},
            },
            "polza_model": {
                "label": "Polza Model",
                "type": "text",
                "default": "deepseek/deepseek-v3.2",
                "show_when": {"ai_provider": "polza"},
            },
            "deepseek_model": {
                "label": "DeepSeek Model",
                "type": "text",
                "default": "deepseek-chat",
                "show_when": {"ai_provider": "deepseek"},
            },
            "local_ai_url": {
                "label": "Local AI URL",
                "type": "text",
                "default": "http://host.docker.internal:1234/v1/chat/completions",
                "show_when": {"ai_provider": "local"},
            },
            "local_ai_model": {
                "label": "Local AI Model",
                "type": "text",
                "default": "yandexgpt-5-lite-8b",
                "show_when": {"ai_provider": "local"},
            },
            "temperature": {
                "label": "Температура",
                "type": "number",
                "default": 0.9,
                "min": 0,
                "max": 2,
                "step": 0.1,
            },
            "max_tokens": {
                "label": "Max Tokens",
                "type": "number",
                "default": 2000,
                "min": -1,
                "max": 8000,
            },
        },
    },
    "imagegen": {
        "name": "ImageGen Worker",
        "icon": "🖼️",
        "description": "Генерация изображений через ComfyUI",
        "settings": {
            "comfyui_url": {
                "label": "ComfyUI API URL",
                "type": "text",
                "default": "http://localhost:5000",
                "show_when": {"provider": "comfyui"},
            },
            "provider": {
                "label": "Провайдер",
                "type": "select",
                "options": ["comfyui", "polza"],
                "default": "comfyui",
            },
            "polza_api_key": {
                "label": "Polza.ai API Key",
                "type": "text",
                "default": "",
                "placeholder": "sk-...",
                "show_when": {"provider": "polza"},
            },
            "polza_model": {
                "label": "Polza Model",
                "type": "text",
                "default": "seedream-v4",
                "show_when": {"provider": "polza"},
            },
            "workflow": {
                "label": "Workflow",
                "type": "select",
                "options": ["turbo_fast", "sdxl_quality", "flux_realism"],
                "default": "turbo_fast",
            },
            "style": {
                "label": "Стиль изображений",
                "type": "select",
                "options": ["stylized", "realistic", "cartoon"],
                "default": "stylized",
            },
            "timeout": {
                "label": "Timeout (сек)",
                "type": "number",
                "default": 120,
                "min": 30,
                "max": 600,
            },
        },
    },
    "import": {
        "name": "Import Worker",
        "icon": "📥",
        "description": "Импорт вакансий из внешних источников",
        "settings": {
            # Duplicate handling
            "skip_duplicates": {
                "label": "Пропускать дубликаты",
                "type": "toggle",
                "default": True,
            },
            "duplicate_key_fields": {
                "label": "Поля для проверки дубликатов",
                "type": "text",
                "default": "city,address,position,service",
            },
            # Processing options
            "auto_start_processing": {
                "label": "Авто-запуск обработки",
                "type": "toggle",
                "default": True,
            },
            "default_relevance": {
                "label": "Актуальность по умолчанию",
                "type": "select",
                "options": ["Да", "Нет"],
                "default": "Да",
            },
            # Relevance check scheduling
            "relevance_check_enabled": {
                "label": "Автопроверка актуальности",
                "type": "toggle",
                "default": False,
            },
            "relevance_check_schedule": {
                "label": "Расписание проверки",
                "type": "select",
                "options": ["every_1h", "every_6h", "every_12h", "every_24h"],
                "default": "every_6h",
                "show_when": {"relevance_check_enabled": True},
            },
        },
    },
    "publisher": {
        "name": "Publisher Worker",
        "icon": "📤",
        "description": "Публикация вакансий на Avito",
        "settings": {
            "yandex_disk_enabled": {
                "label": "Сохранять XML на Яндекс.Диск",
                "type": "toggle",
                "default": True,
            },
            "xml_filename_prefix": {
                "label": "Префикс имени XML",
                "type": "text",
                "default": "avito_export",
            },
            "include_images": {
                "label": "Включать изображения в XML",
                "type": "toggle",
                "default": True,
            },
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# REDIS HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _get_redis_client() -> redis.Redis:
    """Get Redis client."""
    return redis.from_url(settings.redis_url)


def _get_worker_key(worker_name: str) -> str:
    """Get Redis key for worker settings."""
    return f"{WORKER_SETTINGS_PREFIX}{worker_name}"


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def get_all_workers() -> Dict[str, Any]:
    """
    Get all worker definitions with their current settings.
    Returns merged default + saved settings.
    """
    result = {}
    
    try:
        r = _get_redis_client()
        
        for worker_id, worker_def in DEFAULT_SETTINGS.items():
            result[worker_id] = {
                "name": worker_def["name"],
                "icon": worker_def["icon"],
                "description": worker_def["description"],
                "settings_schema": worker_def["settings"],
                "current_values": get_worker_settings(worker_id),
            }
    except Exception as e:
        logger.error(f"Failed to get worker settings: {e}")
        # Return defaults on error
        for worker_id, worker_def in DEFAULT_SETTINGS.items():
            result[worker_id] = {
                "name": worker_def["name"],
                "icon": worker_def["icon"],
                "description": worker_def["description"],
                "settings_schema": worker_def["settings"],
                "current_values": _get_default_values(worker_id),
            }
    
    return result


def get_worker_settings(worker_name: str) -> Dict[str, Any]:
    """
    Get current settings for a specific worker.
    Returns merged default + saved values.
    """
    defaults = _get_default_values(worker_name)
    
    try:
        r = _get_redis_client()
        key = _get_worker_key(worker_name)
        saved = r.get(key)
        
        if saved:
            saved_values = json.loads(saved)
            # Merge with defaults (saved values take precedence)
            defaults.update(saved_values)
    except Exception as e:
        logger.error(f"Failed to get worker settings from Redis: {e}")
    
    return defaults


def get_worker_setting(worker_name: str, setting_name: str, default: Any = None) -> Any:
    """Get a specific setting value for a worker."""
    settings_dict = get_worker_settings(worker_name)
    return settings_dict.get(setting_name, default)


def update_worker_settings(worker_name: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update settings for a specific worker.
    Returns the new merged settings.
    """
    if worker_name not in DEFAULT_SETTINGS:
        raise ValueError(f"Unknown worker: {worker_name}")
    
    # Get current settings
    current = get_worker_settings(worker_name)
    
    # Validate and apply updates
    schema = DEFAULT_SETTINGS[worker_name]["settings"]
    for key, value in updates.items():
        if key in schema:
            # Type validation could be added here
            current[key] = value
    
    # Save to Redis
    try:
        r = _get_redis_client()
        key = _get_worker_key(worker_name)
        r.set(key, json.dumps(current))
        logger.info(f"Updated settings for {worker_name}: {updates}")
    except Exception as e:
        logger.error(f"Failed to save worker settings to Redis: {e}")
        raise
    
    return current


def reset_worker_settings(worker_name: str) -> Dict[str, Any]:
    """Reset a worker's settings to defaults."""
    if worker_name not in DEFAULT_SETTINGS:
        raise ValueError(f"Unknown worker: {worker_name}")
    
    try:
        r = _get_redis_client()
        key = _get_worker_key(worker_name)
        r.delete(key)
        logger.info(f"Reset settings for {worker_name} to defaults")
    except Exception as e:
        logger.error(f"Failed to reset worker settings: {e}")
        raise
    
    return _get_default_values(worker_name)


def _get_default_values(worker_name: str) -> Dict[str, Any]:
    """Extract default values from schema."""
    if worker_name not in DEFAULT_SETTINGS:
        return {}
    
    schema = DEFAULT_SETTINGS[worker_name]["settings"]
    return {key: spec["default"] for key, spec in schema.items()}

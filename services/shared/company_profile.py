"""
AdsGen 2.0 - Company Profile Management
Manages default company settings for XML export
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default profile path (relative to project root)
PROFILE_PATH = Path("data/company_profile.json")

# Default values
DEFAULT_PROFILE = {
    "manager_name": "Менеджер",
    "contact_phone": "",
    "company_name": "Компания",
    "email": "",
    "contact_method": "По телефону и в сообщениях",
    "listing_fee": "Package",
    # Default XML settings
    "industry": "Розничная и оптовая торговля",
    "employment_type": "Полная",
    "job_type": "Гибкий",
    "experience": "Без опыта",
    "pay_period": "за смену",
    "payout_frequency": "Каждый день",
    "tax": "На руки",
    "part_time_job": "Да",
    "age_criteria": "18|65",
    "citizenship_criteria": "Россия",
    "ask_age": "Да",
    "ask_citizenship": "Да",
    "chat_questionnaire": "Проводить",
    "ai_recruter": "Нет",
    "apply_type": "Любые",
    # Default bonuses
    "job_bonuses": ["Униформа", "Обучение"],
    # Default age preferences
    "age_preferences": ["Старше 45 лет", "Для пенсионеров"],
    # Default registration methods
    "registration_method": ["Трудовой договор", "Договор ГПХ с самозанятым"],
    # Default working days
    "working_days_per_week": ["3–4 дня", "5 дней", "6–7 дней"],
    "working_hours_per_day": ["8 часов", "9–10 часов", "11–12 часов"],
    # Auto-publication schedule
    "publication_schedule": {
        "enabled": False,
        "days": [0, 1, 2, 3, 4],  # Mon-Fri (0=Mon, 6=Sun)
        "hours": [9, 12, 15, 18],  # Run at these hours
    },
}


def _ensure_data_dir():
    """Ensure data directory exists."""
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_profile() -> dict:
    """
    Load company profile from file.
    Returns default profile if file doesn't exist.
    """
    try:
        if PROFILE_PATH.exists():
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                profile = json.load(f)
                # Merge with defaults for any missing keys
                return {**DEFAULT_PROFILE, **profile}
    except Exception as e:
        logger.warning(f"Failed to load profile: {e}")
    
    return DEFAULT_PROFILE.copy()


def update_profile(updates: dict) -> dict:
    """
    Update company profile with new values.
    Only updates provided fields, preserves others.
    """
    _ensure_data_dir()
    
    # Load current profile
    current = get_profile()
    
    # Apply updates
    current.update(updates)
    
    # Save to file
    try:
        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        logger.info("Company profile updated")
    except Exception as e:
        logger.error(f"Failed to save profile: {e}")
        raise
    
    return current


def get_profile_field(field: str, default: Optional[str] = None) -> Optional[str]:
    """Get a single field from the profile."""
    profile = get_profile()
    return profile.get(field, default)

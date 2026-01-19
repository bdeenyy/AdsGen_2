"""
AdsGen 2.0 - Test Configuration
Pytest fixtures for mocking database, Celery, and external APIs
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment variables BEFORE any imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DEEPSEEK_API_KEY", "test_key")
os.environ.setdefault("COMFYUI_URL", "http://localhost:8188")


# ═══════════════════════════════════════════════════════════════════════════
# MOCK SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_settings():
    """Mock application settings."""
    settings = MagicMock()
    settings.database_url = "postgresql+asyncpg://test:test@localhost:5432/test"
    settings.redis_url = "redis://localhost:6379/0"
    settings.deepseek_api_key = "test_api_key"
    settings.deepseek_api_url = "https://api.deepseek.com/v1/chat/completions"
    settings.deepseek_model = "deepseek-chat"
    settings.comfyui_url = "http://localhost:8188"
    settings.yandex_disk_token = "test_token"
    settings.yandex_disk_folder = "Test_Folder"
    settings.google_credentials_json = ""
    return settings


# ═══════════════════════════════════════════════════════════════════════════
# MOCK DATABASE
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_session():
    """Mock SQLAlchemy session."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


@pytest.fixture
def mock_vacancy():
    """Create a mock vacancy object."""
    vacancy = MagicMock()
    vacancy.id = "MSK-TEST-001"
    vacancy.city = "Москва"
    vacancy.address = "ул. Тестовая, 1"
    vacancy.position = "Кассир"
    vacancy.profession = "Кассир"
    vacancy.schedule = "5/2"
    vacancy.level = "Уровень 1"
    vacancy.store_type = "Гипермаркет"
    vacancy.service = "Услуга 1"
    vacancy.notes = "Тестовые примечания"
    vacancy.title = None
    vacancy.description = None
    vacancy.image_url = None
    vacancy.status = "pending"
    vacancy.error_message = None
    vacancy.retry_count = 0
    vacancy.manager_name = "Менеджер"
    vacancy.manager_phone = "+7123456789"
    vacancy.company_name = "Тест Компания"
    vacancy.company_email = "test@example.com"
    vacancy.salary_min = 2000
    vacancy.salary_max = 4000
    vacancy.xml_exported = False
    return vacancy


# ═══════════════════════════════════════════════════════════════════════════
# MOCK CELERY
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_celery_app():
    """Mock Celery application."""
    app = MagicMock()
    task = MagicMock()
    task.id = "test-task-id-123"
    app.send_task.return_value = task
    return app


# ═══════════════════════════════════════════════════════════════════════════
# SAMPLE DATA
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_json_data():
    """Sample JSON import data."""
    return [
        {
            "Город": "Москва",
            "Адрес": "ул. Тестовая, 1",
            "Должность": "Кассир",
            "График": "5/2",
            "Уровень ЧТС": "Уровень 1",
            "Актуальность": "Да",
        },
        {
            "Город": "Санкт-Петербург",
            "Адрес": "пр. Невский, 10",
            "Должность": "Продавец",
            "График": "2/2",
            "Актуальность": "Да",
        },
    ]


@pytest.fixture
def sample_invalid_json_data():
    """Invalid JSON import data (missing required fields)."""
    return [
        {"Город": "Москва"},  # Missing position
        {"Должность": "Кассир"},  # Missing city
    ]


# ═══════════════════════════════════════════════════════════════════════════
# DEEPSEEK API MOCK
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_deepseek_response():
    """Mock DeepSeek API response for text generation."""
    return {
        "choices": [
            {
                "message": {
                    "content": '{"title": "Кассир в магазин", "description": "<p>Приглашаем на работу кассира!</p>"}'
                }
            }
        ]
    }


@pytest.fixture
def mock_deepseek_translation_response():
    """Mock DeepSeek API response for translation."""
    return {
        "choices": [
            {
                "message": {
                    "content": "Cashier"
                }
            }
        ]
    }


# ═══════════════════════════════════════════════════════════════════════════
# COMFYUI API MOCK
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_comfyui_response():
    """Mock ComfyUI API response."""
    return {
        "success": True,
        "image_url": "https://disk.yandex.ru/i/test_image.jpg"
    }

"""
AdsGen 2.0 - Celery Application Configuration
Centralized Celery setup with task routing
"""

from celery import Celery

from .config import get_settings


settings = get_settings()

# Create Celery app
celery_app = Celery(
    "adsgen",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# Configure Celery
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    
    # Task routing
    task_routes={
        "services.import_worker.tasks.*": {"queue": "import"},
        "services.textgen_worker.tasks.*": {"queue": "textgen"},
        "services.imagegen_worker.tasks.*": {"queue": "imagegen"},
        "services.validation_worker.tasks.*": {"queue": "validation"},
        "services.publisher_worker.tasks.*": {"queue": "publisher"},
        "services.notification_worker.tasks.*": {"queue": "notification"},
    },
    
    # Retry settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Result backend settings
    result_expires=86400,  # 24 hours
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
    
    # Celery Beat schedule (periodic tasks)
    beat_schedule={
        "sync-all-sources-hourly": {
            "task": "services.import_worker.tasks.sync_all_active_sources",
            "schedule": 3600.0,  # Every hour
        },
        "publisher-auto-export": {
            "task": "services.publisher_worker.tasks.export_to_xml",
            "schedule": 1800.0,  # Every 30 minutes
        },
    },
)

# Auto-discover tasks from worker modules
# Note: autodiscovery is handled by the worker command or via explicit imports
# to avoid dependency hell between microservices.

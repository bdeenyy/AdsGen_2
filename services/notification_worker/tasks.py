"""
AdsGen 2.0 - Notification Worker Tasks
Celery tasks for sending notifications (Telegram, Email)
Optional worker - can be enabled later
"""

import logging
from typing import Optional

import httpx
from celery import shared_task
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from services.shared.config import get_settings
from services.shared.models.vacancy import Vacancy, VacancyStatus
from services.shared.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()

sync_engine = create_engine(
    settings.database_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql+psycopg2")
)


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATION TASKS
# ═══════════════════════════════════════════════════════════════════════════

@celery_app.task
def send_batch_completion_notification(
    batch_id: int,
    total_processed: int,
    total_errors: int,
) -> dict:
    """
    Send notification about batch processing completion.
    """
    message = f"""
✅ Batch processing completed!

📊 Statistics:
- Processed: {total_processed}
- Errors: {total_errors}
- Batch ID: {batch_id}

View details in the admin panel.
    """.strip()
    
    # TODO: Implement Telegram/Email sending
    logger.info(f"Notification: {message}")
    
    return {
        "status": "sent",
        "message": message,
    }


@celery_app.task  
def send_error_notification(
    vacancy_id: str,
    error_message: str,
) -> dict:
    """
    Send notification about processing error.
    """
    message = f"""
❌ Processing error!

Vacancy ID: {vacancy_id}
Error: {error_message}

Please check the vacancy and retry.
    """.strip()
    
    logger.warning(f"Error notification: {message}")
    
    return {
        "status": "sent",
        "message": message,
    }


@celery_app.task
def send_telegram_message(
    chat_id: str,
    message: str,
    bot_token: Optional[str] = None,
) -> dict:
    """
    Send a Telegram message.
    """
    if not bot_token:
        logger.warning("Telegram bot token not configured")
        return {"error": "Bot token not configured"}
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
            )
            
            if response.status_code == 200:
                return {"status": "sent"}
            else:
                return {"error": f"Telegram API error: {response.text}"}
                
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return {"error": str(e)}

"""
AdsGen 2.0 - Validation Worker Tasks
Celery tasks for validating vacancy content against Avito rules
"""

import logging
import re
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
# AVITO RULES & STOP WORDS
# ═══════════════════════════════════════════════════════════════════════════

# Words that are prohibited in Avito ads
STOP_WORDS = [
    # Discrimination
    "только мужчины",
    "только женщины",
    "славянская внешность",
    "без вредных привычек",
    "молодых",
    "до 35 лет",
    "граждане рф",
    
    # Health discrimination (must not require health certificates in ads)
    "медицинская справка",
    "хорошее здоровье",
    "крепкое здоровье",
    "физически здоровым",
    "отсутствие инвалидности",
    
    # Prohibited content
    "гарантированный заработок",
    "пассивный доход",
    "без вложений",
    "легкие деньги",
    "высокий доход без опыта",
    
    # Contact info in title (should be in dedicated fields)
    "телефон",
    "звоните",
    "пишите в",
    "whatsapp",
    "telegram",
    "viber",
]

# Maximum lengths
MAX_TITLE_LENGTH = 50
MIN_DESCRIPTION_LENGTH = 300
MAX_DESCRIPTION_LENGTH = 10000


# ═══════════════════════════════════════════════════════════════════════════
# MAIN TASK
# ═══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=2)
def validate_vacancy_content(self, vacancy_id: str) -> dict:
    """
    Validate vacancy content against Avito rules.
    """
    logger.info(f"Starting validation for vacancy: {vacancy_id}")
    
    with Session(sync_engine) as session:
        vacancy = session.get(Vacancy, vacancy_id)
        
        if not vacancy:
            logger.error(f"Vacancy not found: {vacancy_id}")
            return {"error": "Vacancy not found"}
        
        try:
            vacancy.status = VacancyStatus.VALIDATING
            session.commit()
            
            errors = []
            warnings = []
            
            # 1. Validate title
            title_errors = _validate_title(vacancy.title)
            errors.extend(title_errors)
            
            # 2. Validate description
            desc_errors, desc_warnings = _validate_description(vacancy.description)
            errors.extend(desc_errors)
            warnings.extend(desc_warnings)
            
            # 3. Validate image URL
            image_errors = _validate_image(vacancy.image_url)
            errors.extend(image_errors)
            
            # 4. Check for stop words
            stop_word_errors = _check_stop_words(vacancy.title, vacancy.description)
            errors.extend(stop_word_errors)
            
            if errors:
                vacancy.status = VacancyStatus.ERROR
                vacancy.error_message = "; ".join(errors)
                session.commit()
                
                logger.warning(f"Validation failed for {vacancy_id}: {errors}")
                
                return {
                    "vacancy_id": vacancy_id,
                    "status": "failed",
                    "errors": errors,
                    "warnings": warnings,
                }
            else:
                vacancy.status = VacancyStatus.VALIDATED
                vacancy.error_message = None
                session.commit()
                
                # Trigger publishing
                from services.publisher_worker.tasks import publish_vacancy
                publish_vacancy.delay(vacancy_id)
                
                logger.info(f"Validation passed for {vacancy_id}")
                
                return {
                    "vacancy_id": vacancy_id,
                    "status": "passed",
                    "warnings": warnings,
                }
                
        except Exception as e:
            logger.error(f"Validation error for {vacancy_id}: {e}")
            vacancy.status = VacancyStatus.ERROR
            vacancy.error_message = str(e)
            session.commit()
            
            return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _validate_title(title: Optional[str]) -> list[str]:
    """Validate ad title."""
    errors = []
    
    if not title:
        errors.append("Title is missing")
        return errors
    
    if len(title) > MAX_TITLE_LENGTH:
        errors.append(f"Title too long: {len(title)} chars (max {MAX_TITLE_LENGTH})")
    
    if len(title) < 10:
        errors.append("Title too short (min 10 characters)")
    
    # Check for salary in title (not allowed)
    salary_patterns = [
        r'\d+\s*(руб|₽|р\.)',
        r'от\s+\d+',
        r'до\s+\d+\s*(руб|₽)',
        r'зарплата',
        r'оклад',
        r'выплат',
    ]
    for pattern in salary_patterns:
        if re.search(pattern, title, re.IGNORECASE):
            errors.append("Title should not contain salary information")
            break
    
    # Check for pipe character
    if "|" in title:
        errors.append("Title contains prohibited character '|'")
    
    return errors


def _validate_description(description: Optional[str]) -> tuple[list[str], list[str]]:
    """Validate ad description."""
    errors = []
    warnings = []
    
    if not description:
        errors.append("Description is missing")
        return errors, warnings
    
    # Length checks
    if len(description) < MIN_DESCRIPTION_LENGTH:
        errors.append(f"Description too short: {len(description)} chars (min {MIN_DESCRIPTION_LENGTH})")
    
    if len(description) > MAX_DESCRIPTION_LENGTH:
        errors.append(f"Description too long: {len(description)} chars (max {MAX_DESCRIPTION_LENGTH})")
    
    # Check for pipe character
    if "|" in description:
        warnings.append("Description contains '|' character - may cause issues")
    
    # Check for broken HTML
    open_tags = len(re.findall(r'<[^/][^>]*>', description))
    close_tags = len(re.findall(r'</[^>]+>', description))
    if abs(open_tags - close_tags) > 3:
        warnings.append("Description may have unbalanced HTML tags")
    
    return errors, warnings


def _validate_image(image_url: Optional[str]) -> list[str]:
    """Validate image URL accessibility."""
    errors = []
    
    if not image_url:
        errors.append("Image URL is missing")
        return errors
    
    # Check URL format
    if not image_url.startswith(("http://", "https://")):
        errors.append("Invalid image URL format")
        return errors
    
    # Check image accessibility (HEAD request)
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.head(image_url, follow_redirects=True)
            
            if response.status_code != 200:
                errors.append(f"Image not accessible (HTTP {response.status_code})")
            else:
                # Check content type
                content_type = response.headers.get("content-type", "")
                if not content_type.startswith("image/"):
                    errors.append(f"URL does not point to an image: {content_type}")
                    
    except httpx.TimeoutException:
        errors.append("Image URL timed out")
    except Exception as e:
        errors.append(f"Cannot verify image: {e}")
    
    return errors


def _check_stop_words(title: Optional[str], description: Optional[str]) -> list[str]:
    """Check for prohibited stop words."""
    errors = []
    
    combined_text = f"{title or ''} {description or ''}".lower()
    
    for word in STOP_WORDS:
        if word.lower() in combined_text:
            errors.append(f"Contains prohibited phrase: '{word}'")
    
    return errors

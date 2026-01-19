"""
AdsGen 2.0 - ImageGen Worker Tasks
Celery tasks for generating profession images via ComfyUI
Migrated from avito-vacancies-v3.gs (generateImage, getProfessionImage)
"""

import json
import logging
import random
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

# Default fallback image
FALLBACK_IMAGE = "https://www.avito.ru/static/images/profile/default_profile_140x140.png"


# ═══════════════════════════════════════════════════════════════════════════
# MAIN TASK
# ═══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def generate_vacancy_image(
    self,
    vacancy_id: str,
    gender: Optional[str] = None,
    age: Optional[int] = None
) -> dict:
    """
    Generate image for a vacancy using ComfyUI.
    """
    logger.info(f"Starting image generation for vacancy: {vacancy_id}")
    
    with Session(sync_engine) as session:
        vacancy = session.get(Vacancy, vacancy_id)
        
        if not vacancy:
            logger.error(f"Vacancy not found: {vacancy_id}")
            return {"error": "Vacancy not found"}
        
        try:
            # Update status
            vacancy.status = VacancyStatus.IMAGE_GENERATING
            session.commit()
            
            # Generate random gender/age if not provided
            if not gender:
                gender = random.choice(["man", "woman"])
            if not age:
                age = random.randint(20, 45)
            
            # Build notes from vacancy data
            notes = ""
            if vacancy.notes:
                notes = f"Context from notes: {vacancy.notes}"
            if vacancy.service:
                notes += f". Service context: {vacancy.service}"
            
            # Translate profession to English for ComfyUI
            en_profession = _translate_to_english(vacancy.profession)
            en_notes = _translate_to_english(notes) if notes else None
            
            logger.info(f"Generating image: profession={en_profession}, gender={gender}, age={age}")
            
            # Call ComfyUI
            image_url = _call_comfyui(
                profession=en_profession,
                gender=gender,
                age=age,
                notes=en_notes,
            )
            
            if image_url:
                vacancy.image_url = image_url
                vacancy.status = VacancyStatus.IMAGE_GENERATED
            else:
                vacancy.image_url = FALLBACK_IMAGE
                vacancy.status = VacancyStatus.IMAGE_GENERATED
                logger.warning(f"Using fallback image for {vacancy_id}")
            
            session.commit()
            
            # Trigger validation
            from services.validation_worker.tasks import validate_vacancy_content
            validate_vacancy_content.delay(vacancy_id)
            
            logger.info(f"Image generated for {vacancy_id}: {vacancy.image_url}")
            
            return {
                "vacancy_id": vacancy_id,
                "image_url": vacancy.image_url,
                "status": "success",
            }
            
        except Exception as e:
            logger.error(f"Image generation failed for {vacancy_id}: {e}")
            vacancy.status = VacancyStatus.ERROR
            vacancy.error_message = f"Image generation failed: {e}"
            vacancy.retry_count += 1
            session.commit()
            
            if vacancy.retry_count < 2:
                self.retry(exc=e)
            
            return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# COMFYUI INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

def _call_comfyui(
    profession: str,
    gender: str,
    age: int,
    notes: Optional[str] = None
) -> Optional[str]:
    """
    Call ComfyUI API to generate an image.
    Migrated from generateImage() in avito-vacancies-v3.gs
    """
    if not settings.comfyui_url:
        logger.error("ComfyUI URL not configured")
        return None
    
    payload = {
        "profession": profession,
        "gender": gender,
        "age": age,
        "notes": notes,
    }
    
    try:
        with httpx.Client(timeout=300.0) as client:  # 5 min timeout for generation
            response = client.post(
                f"{settings.comfyui_url}/generate",
                json=payload,
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success") and result.get("image_url"):
                    return result["image_url"]
                else:
                    logger.error(f"ComfyUI error: {result.get('error', 'Unknown error')}")
                    return None
            else:
                logger.error(f"ComfyUI HTTP error: {response.status_code} - {response.text}")
                return None
                
    except httpx.TimeoutException:
        logger.error("ComfyUI request timed out")
        return None
    except Exception as e:
        logger.error(f"ComfyUI request failed: {e}")
        return None


def _check_comfyui_health() -> bool:
    """Check if ComfyUI server is available."""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{settings.comfyui_url}/health")
            if response.status_code == 200:
                result = response.json()
                return result.get("comfyui_available", False)
    except Exception:
        pass
    return False


# ═══════════════════════════════════════════════════════════════════════════
# TRANSLATION
# ═══════════════════════════════════════════════════════════════════════════

def _translate_to_english(text: str) -> str:
    """
    Translate Russian text to English using DeepSeek.
    Migrated from translateToEnglish() in avito-vacancies-v3.gs
    """
    if not text or not settings.deepseek_api_key:
        return text
    
    prompt = f"""Translate the following text strictly to English. The text describes a job position or visual details for an image generation prompt.
Respond ONLY with the translation, no explanations, no quotes.

Text to translate:
{text}"""

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                settings.deepseek_api_url,
                headers={
                    "Authorization": f"Bearer {settings.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.deepseek_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.3,
                },
            )
            
            if response.status_code == 200:
                result = response.json()
                translated = result["choices"][0]["message"]["content"].strip()
                # Clean up artifacts
                return translated.strip('"\'')
            else:
                logger.warning(f"Translation failed: {response.status_code}")
                return text
                
    except Exception as e:
        logger.warning(f"Translation error: {e}")
        return text

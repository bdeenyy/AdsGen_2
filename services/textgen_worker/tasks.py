"""
AdsGen 2.0 - TextGen Worker Tasks
Celery tasks for generating vacancy titles and descriptions using DeepSeek AI
"""

import json
import logging
import random
from typing import Optional

import httpx
from celery import shared_task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from services.shared.config import get_settings
from services.shared.models.vacancy import Vacancy, VacancyStatus
from services.shared.celery_app import celery_app
from .prompts import get_generation_prompt, DESCRIPTION_TEMPLATES

logger = logging.getLogger(__name__)
settings = get_settings()

sync_engine = create_engine(
    settings.database_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql+psycopg2")
)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN TASK
# ═══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def generate_vacancy_text(self, vacancy_id: str) -> dict:
    """
    Generate title and description for a vacancy using DeepSeek AI.
    """
    logger.info(f"Starting text generation for vacancy: {vacancy_id}")
    
    with Session(sync_engine) as session:
        # Get vacancy
        vacancy = session.get(Vacancy, vacancy_id)
        
        if not vacancy:
            logger.error(f"Vacancy not found: {vacancy_id}")
            return {"error": "Vacancy not found"}
        
        try:
            # Update status
            vacancy.status = VacancyStatus.TEXT_GENERATING
            session.commit()
            
            # Generate content using AI
            content = _generate_ai_content(vacancy)
            
            if content:
                vacancy.title = content.get("title")
                vacancy.description = content.get("description")
                vacancy.status = VacancyStatus.TEXT_GENERATED
            else:
                # Fallback to template-based generation
                vacancy.title = _generate_fallback_title(vacancy)
                vacancy.description = _generate_fallback_description(vacancy)
                vacancy.status = VacancyStatus.TEXT_GENERATED
            
            session.commit()
            
            # Trigger image generation
            from services.imagegen_worker.tasks import generate_vacancy_image
            generate_vacancy_image.delay(vacancy_id)
            
            logger.info(f"Text generated successfully for: {vacancy_id}")
            
            return {
                "vacancy_id": vacancy_id,
                "title": vacancy.title,
                "description_length": len(vacancy.description) if vacancy.description else 0,
                "status": "success",
            }
            
        except Exception as e:
            logger.error(f"Text generation failed for {vacancy_id}: {e}")
            vacancy.status = VacancyStatus.ERROR
            vacancy.error_message = str(e)
            vacancy.retry_count += 1
            session.commit()
            
            if vacancy.retry_count < 3:
                self.retry(exc=e)
            
            return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# AI GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def _generate_ai_content(vacancy: Vacancy) -> Optional[dict]:
    """
    Generate title and description using DeepSeek API.
    """
    if not settings.deepseek_api_key:
        logger.warning("DeepSeek API key not configured, using fallback")
        return None
    
    # Build prompt
    prompt = get_generation_prompt(
        profession=vacancy.profession,
        address=f"{vacancy.city}, {vacancy.address}",
        salary="от 200 рублей/час",
        service=vacancy.service or "",
        store_type=vacancy.store_type or "",
    )
    
    # Call DeepSeek API
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                settings.deepseek_api_url,
                headers={
                    "Authorization": f"Bearer {settings.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.deepseek_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0.9,
                },
            )
            
            if response.status_code != 200:
                logger.error(f"DeepSeek API error: {response.status_code} - {response.text}")
                return None
            
            result = response.json()
            ai_text = result["choices"][0]["message"]["content"].strip()
            
            # Parse JSON response with multiple fallback strategies
            content = _parse_ai_response(ai_text)
            
            if not content:
                logger.warning("Failed to parse AI response, using fallback")
                return None
            
            # Clean up and validate content
            if content.get("title"):
                content["title"] = content["title"].replace("|", "").strip()[:100]
            
            if content.get("description"):
                content["description"] = content["description"].replace("|", "").strip()
            
            # Validate required fields
            if not content.get("title") or not content.get("description"):
                logger.warning("AI response missing required fields (title or description)")
                return None
            
            return content
            
    except Exception as e:
        logger.error(f"DeepSeek API call failed: {e}")
        return None


def _parse_ai_response(ai_text: str) -> Optional[dict]:
    """
    Parse AI response with multiple fallback strategies.
    Returns parsed dict or None if parsing fails.
    """
    if not ai_text:
        return None
    
    # Strategy 1: Try to parse as-is JSON
    try:
        return json.loads(ai_text)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Remove markdown code blocks
    cleaned = ai_text
    for marker in ["```json", "```", "```python", "```javascript"]:
        if marker in cleaned:
            # Extract content between markers
            parts = cleaned.split(marker)
            if len(parts) >= 3:
                cleaned = parts[1].strip()
            else:
                cleaned = cleaned.replace(marker, "").strip()
    
    # Strategy 3: Try to find JSON object/array
    import re
    json_pattern = r'\{[^{}]*\{[^{}]*\}[^{}]*\}|\{[^{}]*\}'
    matches = re.findall(json_pattern, cleaned, re.DOTALL)
    
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    # Strategy 4: Try to parse as single-line JSON without formatting
    try:
        # Remove newlines and extra spaces
        single_line = ' '.join(cleaned.split())
        return json.loads(single_line)
    except json.JSONDecodeError:
        pass
    
    logger.error(f"Failed to parse AI response after all strategies: {ai_text[:200]}...")
    return None


# ═══════════════════════════════════════════════════════════════════════════
# FALLBACK GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def _generate_fallback_title(vacancy: Vacancy) -> str:
    """Generate a simple title without AI."""
    bases = [
        vacancy.profession,
        f"{vacancy.profession} в магазин",
        f"{vacancy.profession} в ТЦ",
    ]
    
    suffixes = [
        "",
        " без опыта",
        ", ежедневные выплаты",
    ]
    
    title = random.choice(bases) + random.choice(suffixes)
    return title[:100]


def _generate_fallback_description(vacancy: Vacancy) -> str:
    """Generate a template-based description without AI."""
    template = DESCRIPTION_TEMPLATES.get(vacancy.profession, {})
    
    duties = template.get("duties", ["<p>Работа в магазине</p>"])
    advantages = template.get("advantages", ["<p>Ежедневные выплаты</p>"])
    
    duty = random.choice(duties)
    adv = random.choice(advantages)
    
    description = f"""
    <p><strong>{vacancy.profession}</strong></p>
    <p>Приглашаем в нашу команду на позицию <strong>{vacancy.profession}</strong>!</p>
    <p>Адрес: {vacancy.city}, {vacancy.address}</p>
    <h3>Обязанности:</h3>
    {duty}
    <h3>Мы предлагаем:</h3>
    {adv}
    <p>Звоните или пишите прямо сейчас! 📞</p>
    """.strip()
    
    return description

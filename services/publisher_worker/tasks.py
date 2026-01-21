"""
AdsGen 2.0 - Publisher Worker Tasks
Celery tasks for publishing vacancies to Avito (XML export and API)
Migrated from genXML.gs
"""

import logging
import html
from datetime import datetime
from typing import Optional

import httpx
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.shared.config import get_settings
from services.shared.database import get_sync_engine
from services.shared.models.vacancy import Vacancy, VacancyStatus
from services.shared.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()

# Sync engine from shared module
sync_engine = get_sync_engine()


# ═══════════════════════════════════════════════════════════════════════════
# MAIN TASKS
# ═══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=2)
def publish_vacancy(self, vacancy_id: str) -> dict:
    """
    Mark vacancy as ready for publication.
    Actual publishing happens in batch via export_to_xml.
    """
    logger.info(f"Publishing vacancy: {vacancy_id}")
    
    with Session(sync_engine) as session:
        vacancy = session.get(Vacancy, vacancy_id)
        
        if not vacancy:
            return {"error": "Vacancy not found"}
        
        vacancy.status = VacancyStatus.PUBLISHED
        vacancy.xml_exported = False  # Will be true after XML export
        session.commit()
        
        return {
            "vacancy_id": vacancy_id,
            "status": "ready_for_export",
        }


@celery_app.task
def export_to_xml(vacancy_ids: Optional[list[str]] = None) -> dict:
    """
    Export vacancies to Avito XML format and upload to Yandex Disk.
    """
    logger.info("Starting XML export")
    
    with Session(sync_engine) as session:
        # Build query
        if vacancy_ids:
            stmt = select(Vacancy).where(Vacancy.id.in_(vacancy_ids))
        else:
            # Export all validated/published vacancies
            stmt = select(Vacancy).where(
                Vacancy.status.in_([VacancyStatus.VALIDATED, VacancyStatus.PUBLISHED])
            ).where(Vacancy.xml_exported == False)
        
        vacancies = session.execute(stmt).scalars().all()
        
        if not vacancies:
            logger.info("No vacancies to export")
            return {"exported": 0, "xml": None}
        
        # Build XML
        xml_content = _build_xml(vacancies)
        
        # Generate filename
        filename = f"Работа-Вакансии-{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
        
        # Upload to Yandex Disk
        yandex_url = None
        try:
            yandex_url = _upload_to_yandex_disk(xml_content, filename)
            logger.info(f"Uploaded XML to Yandex Disk: {yandex_url}")
        except Exception as e:
            logger.error(f"Failed to upload to Yandex Disk: {e}")
            # Save locally as fallback
            try:
                local_path = f"data/{filename}"
                with open(local_path, "w", encoding="utf-8") as f:
                    f.write(xml_content)
                logger.info(f"Saved XML locally: {local_path}")
            except Exception as local_err:
                logger.error(f"Failed to save locally: {local_err}")
        
        # Mark as exported
        for vacancy in vacancies:
            vacancy.xml_exported = True
        
        session.commit()
        
        logger.info(f"Exported {len(vacancies)} vacancies to XML")
        
        return {
            "exported": len(vacancies),
            "filename": filename,
            "yandex_disk_url": yandex_url,
            "xml_length": len(xml_content),
        }


def _upload_to_yandex_disk(content: str, filename: str) -> str:
    """
    Upload XML content to Yandex Disk.
    Returns public URL of the uploaded file.
    """
    token = settings.yandex_disk_token
    if not token or token == "your_yandex_disk_token_here":
        raise ValueError("YANDEX_DISK_TOKEN not configured")
    
    base_folder = settings.yandex_disk_folder or "Картинки_Авито"
    folder_path = f"{base_folder}/XML"
    file_path = f"{folder_path}/{filename}"
    
    headers = {"Authorization": f"OAuth {token}"}
    
    with httpx.Client(timeout=60.0) as client:
        # 1. Ensure folder exists
        client.put(
            f"https://cloud-api.yandex.net/v1/disk/resources?path={folder_path}",
            headers=headers,
        )
        
        # 2. Get upload URL
        resp = client.get(
            f"https://cloud-api.yandex.net/v1/disk/resources/upload?path={file_path}&overwrite=true",
            headers=headers,
        )
        resp.raise_for_status()
        upload_url = resp.json()["href"]
        
        # 3. Upload file
        upload_resp = client.put(
            upload_url,
            content=content.encode("utf-8"),
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
        upload_resp.raise_for_status()
        
        # 4. Publish and get public URL
        client.put(
            f"https://cloud-api.yandex.net/v1/disk/resources/publish?path={file_path}",
            headers=headers,
        )
        
        # 5. Get public link
        meta_resp = client.get(
            f"https://cloud-api.yandex.net/v1/disk/resources?path={file_path}",
            headers=headers,
        )
        meta_resp.raise_for_status()
        public_url = meta_resp.json().get("public_url", f"disk:/{file_path}")
        
        return public_url


# ═══════════════════════════════════════════════════════════════════════════
# XML GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def _build_xml(vacancies: list[Vacancy]) -> str:
    """
    Build Avito XML from vacancies.
    Migrated from buildAdXml() in genXML.gs
    """
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_parts.append('<Ads formatVersion="3" target="Avito.ru">')
    
    for vacancy in vacancies:
        xml_parts.append(_build_ad_xml(vacancy))
    
    xml_parts.append('</Ads>')
    
    return '\n'.join(xml_parts)


def _build_ad_xml(vacancy: Vacancy) -> str:
    """Build XML for a single ad using Avito format."""
    from services.shared.company_profile import get_profile
    from services.shared.avito_mappings import get_industry_for_profession, map_experience, map_schedule_to_job_type
    
    profile = get_profile()
    ad_xml = ['\t<Ad>']
    
    # ID
    ad_xml.append(f'\t\t<Id>{_escape_xml(vacancy.id)}</Id>')
    
    # Listing fee
    ad_xml.append(f'\t\t<ListingFee>{profile.get("listing_fee", "Package")}</ListingFee>')
    ad_xml.append('\t\t<AvitoId></AvitoId>')
    
    # Manager info (from profile or vacancy)
    manager_name = vacancy.manager_name or profile.get("manager_name", "")
    contact_phone = vacancy.manager_phone or profile.get("contact_phone", "")
    ad_xml.append(f'\t\t<ManagerName>{_escape_xml(manager_name)}</ManagerName>')
    ad_xml.append(f'\t\t<ContactPhone>{_escape_xml(contact_phone)}</ContactPhone>')
    
    # Images
    if vacancy.image_url:
        ad_xml.append('\t\t<Images>')
        for url in vacancy.image_url.split(' | '):
            url = url.strip()
            if url:
                ad_xml.append(f'\t\t\t<Image url="{_escape_xml(url)}"/>')
        ad_xml.append('\t\t</Images>')
    
    # Address (city + address if available)
    full_address = vacancy.address or vacancy.city or ""
    ad_xml.append(f'\t\t<Address>{_escape_xml(full_address)}</Address>')
    
    # Contact method
    contact_method = profile.get("contact_method", "По телефону и в сообщениях")
    ad_xml.append(f'\t\t<ContactMethod>{contact_method}</ContactMethod>')
    
    # Category (always Вакансии)
    ad_xml.append('\t\t<Category>Вакансии</Category>')
    
    # Industry (auto-mapped from profession)
    industry = get_industry_for_profession(vacancy.profession)
    ad_xml.append(f'\t\t<Industry>{_escape_xml(industry)}</Industry>')
    
    # Title
    title = vacancy.title or vacancy.profession or vacancy.position or ""
    ad_xml.append(f'\t\t<Title>{_escape_xml(title)}</Title>')
    
    # Employment type
    employment_type = profile.get("employment_type", "Полная")
    ad_xml.append(f'\t\t<EmploymentType>{employment_type}</EmploymentType>')
    
    # Job type (schedule)
    job_type = map_schedule_to_job_type(vacancy.schedule) if vacancy.schedule else profile.get("job_type", "Гибкий")
    ad_xml.append(f'\t\t<JobType>{job_type}</JobType>')
    
    # Working days per week
    working_days = profile.get("working_days_per_week", ["3–4 дня", "5 дней", "6–7 дней"])
    ad_xml.append('\t\t<WorkingDaysPerWeek>')
    for opt in working_days:
        ad_xml.append(f'\t\t\t<Option>{opt}</Option>')
    ad_xml.append('\t\t</WorkingDaysPerWeek>')
    
    # Working hours per day
    working_hours = profile.get("working_hours_per_day", ["8 часов", "9–10 часов", "11–12 часов"])
    ad_xml.append('\t\t<WorkingDaysPerDay>')
    for opt in working_hours:
        ad_xml.append(f'\t\t\t<Option>{opt}</Option>')
    ad_xml.append('\t\t</WorkingDaysPerDay>')
    
    # Experience
    experience = map_experience(vacancy.level) if vacancy.level else profile.get("experience", "Без опыта")
    ad_xml.append(f'\t\t<Experience>{experience}</Experience>')
    
    # Description (CDATA)
    if vacancy.description:
        ad_xml.append(f'\t\t<Description>{_escape_xml(vacancy.description)}</Description>')
    
    # Salary
    if vacancy.salary_min or vacancy.salary_max:
        ad_xml.append('\t\t<SalaryRange>')
        if vacancy.salary_min:
            ad_xml.append(f'\t\t\t<From>{vacancy.salary_min}</From>')
        if vacancy.salary_max:
            ad_xml.append(f'\t\t\t<To>{vacancy.salary_max}</To>')
        ad_xml.append('\t\t</SalaryRange>')
    
    # Pay period and frequency
    ad_xml.append(f'\t\t<PayPeriod>{profile.get("pay_period", "за смену")}</PayPeriod>')
    ad_xml.append(f'\t\t<PayoutFrequency>{profile.get("payout_frequency", "Каждый день")}</PayoutFrequency>')
    ad_xml.append(f'\t\t<Tax>{profile.get("tax", "На руки")}</Tax>')
    
    # Job bonuses
    bonuses = profile.get("job_bonuses", ["Униформа", "Обучение"])
    ad_xml.append('\t\t<JobBonuses>')
    for bonus in bonuses:
        ad_xml.append(f'\t\t\t<Option>{bonus}</Option>')
    ad_xml.append('\t\t</JobBonuses>')
    
    # Profession
    ad_xml.append(f'\t\t<Profession>{_escape_xml(vacancy.profession)}</Profession>')
    
    # Age preferences
    age_prefs = profile.get("age_preferences", ["Старше 45 лет", "Для пенсионеров"])
    ad_xml.append('\t\t<AgePreferences>')
    for pref in age_prefs:
        ad_xml.append(f'\t\t\t<Option>{pref}</Option>')
    ad_xml.append('\t\t</AgePreferences>')
    
    # Part time
    ad_xml.append(f'\t\t<PartTimeJob>{profile.get("part_time_job", "Да")}</PartTimeJob>')
    
    # Registration method
    reg_methods = profile.get("registration_method", ["Трудовой договор"])
    ad_xml.append('\t\t<RegistrationMethod>')
    for method in reg_methods:
        ad_xml.append(f'\t\t\t<Option>{method}</Option>')
    ad_xml.append('\t\t</RegistrationMethod>')
    
    # Apply type
    ad_xml.append(f'\t\t<ApplyType>{profile.get("apply_type", "Любые")}</ApplyType>')
    
    # Age/Citizenship criteria
    ad_xml.append(f'\t\t<AgeCriteria>{profile.get("age_criteria", "18|65")}</AgeCriteria>')
    ad_xml.append(f'\t\t<CitizenshipCriteria>{profile.get("citizenship_criteria", "Россия")}</CitizenshipCriteria>')
    
    # Optional empty fields (for specific industries)
    ad_xml.append('\t\t<MedicalBook></MedicalBook>')
    ad_xml.append('\t\t<FoodProductionShopType></FoodProductionShopType>')
    ad_xml.append('\t\t<RetailEquipmentType></RetailEquipmentType>')
    ad_xml.append('\t\t<EateryType></EateryType>')
    ad_xml.append('\t\t<RetailShopType></RetailShopType>')
    ad_xml.append('\t\t<Cuisine></Cuisine>')
    ad_xml.append('\t\t<CleaningJobSiteType></CleaningJobSiteType>')
    
    # Vacancy code (external reference)
    vacancy_code = f"{vacancy.city}_{vacancy.profession}_{vacancy.level or 'стандарт'}"
    ad_xml.append(f'\t\t<VacancyCode>{_escape_xml(vacancy_code)}</VacancyCode>')
    
    # Salary display
    ad_xml.append('\t\t<ThereIsSalary>Нет</ThereIsSalary>')
    
    # Ask questions
    ad_xml.append(f'\t\t<AskAge>{profile.get("ask_age", "Да")}</AskAge>')
    
    # Email
    email = vacancy.company_email or profile.get("email", "")
    ad_xml.append(f'\t\t<EMail>{_escape_xml(email)}</EMail>')
    
    # Chat questionnaire
    ad_xml.append(f'\t\t<ChatQuestionnaire>{profile.get("chat_questionnaire", "Проводить")}</ChatQuestionnaire>')
    
    # Company name
    company = vacancy.company_name or profile.get("company_name", "")
    ad_xml.append(f'\t\t<CompanyName>{_escape_xml(company)}</CompanyName>')
    
    # Status fields
    ad_xml.append('\t\t<AvitoDateEnd></AvitoDateEnd>')
    if vacancy.salary_max:
        ad_xml.append(f'\t\t<Price>{vacancy.salary_max}</Price>')
    ad_xml.append(f'\t\t<AskCitizenship>{profile.get("ask_citizenship", "Да")}</AskCitizenship>')
    ad_xml.append('\t\t<AvitoStatus>Активно</AvitoStatus>')
    ad_xml.append(f'\t\t<AIRecruter>{profile.get("ai_recruter", "Нет")}</AIRecruter>')
    
    ad_xml.append('\t</Ad>')
    
    return '\n'.join(ad_xml)


def _escape_xml(text: str) -> str:
    """Escape special XML characters."""
    if not text:
        return ""
    return html.escape(str(text))

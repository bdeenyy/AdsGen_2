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
from sqlalchemy import create_engine, select
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
    Export vacancies to Avito XML format.
    Migrated from genXML.gs
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
        
        # Save to disk or upload
        filename = f"Работа-Вакансии-{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
        
        # TODO: Upload to Yandex Disk or save locally
        # For now, just mark as exported
        for vacancy in vacancies:
            vacancy.xml_exported = True
        
        session.commit()
        
        logger.info(f"Exported {len(vacancies)} vacancies to XML")
        
        return {
            "exported": len(vacancies),
            "filename": filename,
            "xml_length": len(xml_content),
        }


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
    """Build XML for a single ad."""
    ad_xml = ['\t<Ad>']
    
    # ID
    ad_xml.append(f'\t\t<Id>{_escape_xml(vacancy.id)}</Id>')
    
    # AdType
    ad_xml.append('\t\t<AdType>Package</AdType>')
    
    # Manager info
    ad_xml.append(f'\t\t<ManagerName>{_escape_xml(vacancy.manager_name)}</ManagerName>')
    ad_xml.append(f'\t\t<ContactPhone>{_escape_xml(vacancy.manager_phone)}</ContactPhone>')
    
    # Images
    if vacancy.image_url:
        ad_xml.append('\t\t<Images>')
        for url in vacancy.image_url.split(' | '):
            url = url.strip()
            if url:
                ad_xml.append(f'\t\t\t<Image url="{_escape_xml(url)}"/>')
        ad_xml.append('\t\t</Images>')
    
    # Address
    ad_xml.append(f'\t\t<Address>{_escape_xml(vacancy.city)}</Address>')
    
    # Contact method
    ad_xml.append('\t\t<ContactMethod>По телефону и в сообщениях</ContactMethod>')
    
    # Category
    ad_xml.append('\t\t<Category>Вакансии</Category>')
    ad_xml.append('\t\t<Industry>Розничная и оптовая торговля</Industry>')
    
    # Title
    ad_xml.append(f'\t\t<Title>{_escape_xml(vacancy.title or vacancy.profession)}</Title>')
    
    # Employment details
    ad_xml.append('\t\t<EmploymentType>Полная</EmploymentType>')
    ad_xml.append('\t\t<Schedule>Гибкий</Schedule>')
    
    # Work schedule
    ad_xml.append('\t\t<WorkDays>')
    ad_xml.append('\t\t\t<Option>3–4 дня</Option>')
    ad_xml.append('\t\t\t<Option>5 дней</Option>')
    ad_xml.append('\t\t\t<Option>6–7 дней</Option>')
    ad_xml.append('\t\t</WorkDays>')
    
    ad_xml.append('\t\t<ShiftDuration>')
    ad_xml.append('\t\t\t<Option>8 часов</Option>')
    ad_xml.append('\t\t\t<Option>9–10 часов</Option>')
    ad_xml.append('\t\t\t<Option>11–12 часов</Option>')
    ad_xml.append('\t\t</ShiftDuration>')
    
    # Experience
    ad_xml.append('\t\t<Experience>Без опыта</Experience>')
    
    # Description
    if vacancy.description:
        ad_xml.append(f'\t\t<Description><![CDATA[{vacancy.description}]]></Description>')
    
    # Salary
    if vacancy.salary_min or vacancy.salary_max:
        ad_xml.append('\t\t<SalaryRange>')
        if vacancy.salary_min:
            ad_xml.append(f'\t\t\t<From>{vacancy.salary_min}</From>')
        if vacancy.salary_max:
            ad_xml.append(f'\t\t\t<To>{vacancy.salary_max}</To>')
        ad_xml.append('\t\t</SalaryRange>')
    
    ad_xml.append('\t\t<SalaryType>за смену</SalaryType>')
    ad_xml.append('\t\t<PaymentFrequency>Каждый день</PaymentFrequency>')
    ad_xml.append('\t\t<SalaryPaymentType>На руки</SalaryPaymentType>')
    
    # Benefits
    ad_xml.append('\t\t<Bonuses>')
    ad_xml.append('\t\t\t<Option>Униформа</Option>')
    ad_xml.append('\t\t\t<Option>Парковка</Option>')
    ad_xml.append('\t\t\t<Option>Зоны отдыха</Option>')
    ad_xml.append('\t\t\t<Option>Обучение</Option>')
    ad_xml.append('\t\t</Bonuses>')
    
    # Profession
    ad_xml.append(f'\t\t<Profession>{_escape_xml(vacancy.profession)}</Profession>')
    
    # Hiring categories
    ad_xml.append('\t\t<HiringCategories>')
    ad_xml.append('\t\t\t<Option>Старше 45 лет</Option>')
    ad_xml.append('\t\t\t<Option>С нарушениями здоровья</Option>')
    ad_xml.append('\t\t\t<Option>Для пенсионеров</Option>')
    ad_xml.append('\t\t</HiringCategories>')
    
    # Other fields
    ad_xml.append('\t\t<ExpensesCompensation>Да</ExpensesCompensation>')
    
    ad_xml.append('\t\t<FormOfEmployment>')
    ad_xml.append('\t\t\t<Option>Трудовой договор</Option>')
    ad_xml.append('\t\t\t<Option>Договор ГПХ с ИП</Option>')
    ad_xml.append('\t\t\t<Option>Договор ГПХ с самозанятым</Option>')
    ad_xml.append('\t\t\t<Option>Договор ГПХ с физлицом</Option>')
    ad_xml.append('\t\t</FormOfEmployment>')
    
    ad_xml.append('\t\t<Gender>Любые</Gender>')
    ad_xml.append('\t\t<AgeRange>18|65</AgeRange>')
    ad_xml.append('\t\t<Citizenship>Россия</Citizenship>')
    
    # External ID
    external_id = f"{vacancy.city}_{vacancy.position}_{vacancy.level or 'unknown'}"
    ad_xml.append(f'\t\t<ExternalId>{_escape_xml(external_id)}</ExternalId>')
    
    # Company info
    ad_xml.append('\t\t<AllowEmail>Нет</AllowEmail>')
    ad_xml.append('\t\t<AllowMails>Да</AllowMails>')
    ad_xml.append(f'\t\t<Email>{_escape_xml(vacancy.company_email)}</Email>')
    ad_xml.append('\t\t<ValidateCalls>Проводить</ValidateCalls>')
    ad_xml.append(f'\t\t<CompanyName>{_escape_xml(vacancy.company_name)}</CompanyName>')
    ad_xml.append('\t\t<AllowSearches>Да</AllowSearches>')
    ad_xml.append('\t\t<ListingFee>Активно</ListingFee>')
    ad_xml.append('\t\t<LeadGeneration>Нет</LeadGeneration>')
    
    ad_xml.append('\t</Ad>')
    
    return '\n'.join(ad_xml)


def _escape_xml(text: str) -> str:
    """Escape special XML characters."""
    if not text:
        return ""
    return html.escape(str(text))

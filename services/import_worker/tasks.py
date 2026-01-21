"""
AdsGen 2.0 - Import Worker Tasks
Celery tasks for importing vacancy data from JSON
"""

import logging
from datetime import datetime
from typing import Optional, List

import pandas as pd
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.shared.config import get_settings
from services.shared.database import get_sync_engine
from services.shared.mappings import (
    ALLOWED_CITIES,
    generate_vacancy_id,
    get_profession,
)
from services.shared.models.vacancy import Vacancy, VacancyStatus
from services.shared.models.import_batch import ImportBatch, ImportSource, ImportStatus
from services.shared.celery_app import celery_app
from services.shared.utils import GoogleSheetsService

logger = logging.getLogger(__name__)
settings = get_settings()

# Sync engine from shared module
sync_engine = get_sync_engine()


# ═══════════════════════════════════════════════════════════════════════════
# MAIN IMPORT TASK
# ═══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_json_import(self, data: list[dict], cities_filter: Optional[List[str]] = None) -> dict:
    """
    Process JSON data import (from GAS thin client or direct API call).
    """
    logger.info(f"Starting JSON import: {len(data)} rows")
    
    try:
        df = pd.DataFrame(data)
        result = _process_dataframe(df, ImportSource.CSV, "JSON_PUSH", cities_filter)
        
        if result["processed"] > 0:
            start_batch_processing.delay("pending", result["processed"])
        
        return result
    except Exception as e:
        logger.error(f"JSON import failed: {e}")
        self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def import_spreadsheet(
    self, 
    spreadsheet_input: str, 
    sheet_name: Optional[str] = None, 
    cities_filter: Optional[List[str]] = None,
    column_mapping: Optional[dict] = None
) -> dict:
    """
    Import vacancies from a Google Spreadsheet (by ID or URL).
    """
    logger.info(f"Starting Google Sheets import: {spreadsheet_input} (sheet: {sheet_name})")
    
    try:
        if not settings.google_credentials_json:
            raise ValueError("GOOGLE_CREDENTIALS_JSON not configured")
            
        gs_service = GoogleSheetsService(settings.google_credentials_json)
        data = gs_service.get_sheet_data(spreadsheet_input, sheet_name)
        
        logger.info(f"Fetched {len(data)} rows from Google Sheets")
        
        df = pd.DataFrame(data)
        result = _process_dataframe(df, ImportSource.GOOGLE_SHEETS, spreadsheet_input, cities_filter, column_mapping)
        
        if result["processed"] > 0:
            start_batch_processing.delay("pending", result["processed"])
            
        return result
    except Exception as e:
        logger.error(f"Google Sheets import failed: {e}")
        self.retry(exc=e)


# ═══════════════════════════════════════════════════════════════════════════
# BATCH PROCESSING
# ═══════════════════════════════════════════════════════════════════════════

@celery_app.task
def start_batch_processing(status_filter: str = "pending", limit: int = 50) -> dict:
    """
    Start batch processing for vacancies.
    """
    from services.textgen_worker.tasks import generate_vacancy_text
    
    with Session(sync_engine) as session:
        stmt = select(Vacancy).where(Vacancy.status == VacancyStatus.PENDING).limit(limit)
        vacancies = session.execute(stmt).scalars().all()
        
        triggered = 0
        for vacancy in vacancies:
            vacancy.status = VacancyStatus.TEXT_GENERATING
            session.commit()
            generate_vacancy_text.delay(vacancy.id)
            triggered += 1
        
        return {"triggered": triggered, "status": "completed"}


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _process_dataframe(
    df: pd.DataFrame,
    source_type: ImportSource,
    source_name: str,
    cities_filter: Optional[List[str]] = None,
    column_mapping: Optional[dict] = None
) -> dict:
    """
    Process a DataFrame and create Vacancy records.
    """
    allowed_cities = cities_filter if cities_filter else ALLOWED_CITIES
    
    # Normalize column names
    df.columns = [str(col).strip() for col in df.columns]
    logger.info(f"Normalized columns: {list(df.columns)}")
    
    if column_mapping:
        # Use provided mapping (Source -> Internal)
        # We must also normalize the mapping keys because we normalized df.columns above
        normalized_mapping = {str(k).strip(): v for k, v in column_mapping.items()}
        logger.info(f"Using provided column mapping: {column_mapping} (Normalized: {normalized_mapping})")
        df = df.rename(columns=normalized_mapping)
    else:
        # Use default mapping
        default_mapping = {
            "ТК": "tk",
            "Адрес": "address",
            "Город": "city",
            "Должность": "position",
            "Уровень ЧТС": "level",
            "График": "schedule",
            "Описание Графика": "schedule",
            "Описание графика": "schedule",
            "Тип ТК": "store_type",
            "Услуга": "service",
            "Примечания": "notes",
            "Комментарий": "notes",
            "Актуальность": "relevance",
            "Аткуальна ли вакансия?": "relevance",
            "Актуальна ли вакансия?": "relevance",
        }
        df = df.rename(columns=default_mapping)
    
    logger.info(f"Renamed columns: {list(df.columns)}")
    
    required = ["city", "position"]
    for col in required:
        if col not in df.columns:
            logger.error(f"Missing required column: {col}. Available: {list(df.columns)}")
            raise ValueError(f"Missing required column: {col}")
    
    processed = 0
    skipped = 0
    errors = 0
    
    with Session(sync_engine) as session:
        batch = ImportBatch(
            source_type=source_type,
            filename=source_name,
            total_rows=len(df),
            status=ImportStatus.PROCESSING,
        )
        session.add(batch)
        session.commit()
        
        for idx, row in df.iterrows():
            try:
                city = str(row.get("city", "")).strip()
                if city and city not in allowed_cities:
                    skipped += 1
                    continue
                
                position = str(row.get("position", "")).strip()
                profession = get_profession(position)
                
                if not profession:
                    skipped += 1
                    continue
                
                relevance = row.get("relevance", "")
                if relevance:
                    rel_str = str(relevance).lower().strip()
                    if rel_str not in ["да", "актуально", "yes"]:
                        skipped += 1
                        continue
                
                vacancy_id = generate_vacancy_id(city)
                address = str(row.get("address", "")).strip()
                
                vacancy = Vacancy(
                    id=vacancy_id,
                    city=city,
                    address=address,
                    position=position,
                    profession=profession,
                    schedule=str(row.get("schedule", "")).strip() or None,
                    level=str(row.get("level", "")).strip() or None,
                    store_type=str(row.get("store_type", "")).strip() or None,
                    service=str(row.get("service", "")).strip() or None,
                    notes=str(row.get("notes", "")).strip() or None,
                    status=VacancyStatus.PENDING,
                )
                
                session.add(vacancy)
                processed += 1
                
                if processed % 50 == 0:
                    session.commit()
                    
            except Exception as e:
                logger.error(f"Error processing row {idx}: {e}")
                errors += 1
        
        session.commit()
        batch_id = batch.id  # Access ID while session is open
        batch.processed_rows = processed
        batch.skipped_rows = skipped
        batch.error_rows = errors
        batch.status = ImportStatus.COMPLETED
        batch.completed_at = datetime.utcnow()
        session.commit()
    
    return {
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "total": len(df),
        "batch_id": batch_id,
    }

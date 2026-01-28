"""
AdsGen 2.0 - Import Worker Tasks
Celery tasks for importing vacancy data from JSON
"""

import hashlib
import logging
from datetime import datetime
from typing import Optional, List, Set

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
def start_batch_processing(status_filter: str = "PENDING", limit: int = 50) -> dict:
    """
    Start batch processing for vacancies.
    Triggers text generation for all vacancies with specified status.
    
    Args:
        status_filter: Status to filter by (PENDING, TEXT_GENERATED, IMAGE_GENERATED, etc.)
        limit: Maximum number of vacancies to process
    """
    from services.textgen_worker.tasks import generate_vacancy_text
    from services.imagegen_worker.tasks import generate_vacancy_image
    
    # Convert string to enum
    try:
        target_status = VacancyStatus(status_filter.upper())
    except ValueError:
        target_status = VacancyStatus.PENDING
    
    with Session(sync_engine) as session:
        stmt = select(Vacancy).where(Vacancy.status == target_status).limit(limit)
        vacancies = session.execute(stmt).scalars().all()
        
        triggered = 0
        for vacancy in vacancies:
            if target_status == VacancyStatus.PENDING:
                # Start text generation
                vacancy.status = VacancyStatus.TEXT_GENERATING
                session.commit()
                generate_vacancy_text.delay(vacancy.id)
                triggered += 1
            elif target_status == VacancyStatus.TEXT_GENERATED:
                # Start image generation
                vacancy.status = VacancyStatus.IMAGE_GENERATING
                session.commit()
                generate_vacancy_image.delay(vacancy.id)
                triggered += 1
        
        logger.info(f"Batch processing: triggered {triggered} tasks for status {status_filter}")
        return {"triggered": triggered, "status_filter": status_filter, "status": "completed"}


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _process_dataframe(
    df: pd.DataFrame,
    source_type: ImportSource,
    source_name: str,
    cities_filter: Optional[List[str]] = None,
    column_mapping: Optional[dict] = None,
    source_id: Optional[str] = None  # ID источника для дедупликации
) -> dict:
    """
    Process a DataFrame and create Vacancy records.
    With deduplication support when source_id is provided.
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
    updated = 0
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
                is_relevant = True
                if relevance:
                    rel_str = str(relevance).lower().strip()
                    is_relevant = rel_str in ["да", "актуально", "yes"]
                    if not is_relevant and not source_id:
                        # Skip non-relevant only for non-sync imports
                        skipped += 1
                        continue
                
                address = str(row.get("address", "")).strip()
                
                # Generate row hash for deduplication
                row_hash = hashlib.md5(f"{city}|{address}|{position}".encode()).hexdigest()
                
                # Check for existing vacancy by hash OR by city+address+position
                existing = None
                if source_id:
                    # First try to find by source_id + hash
                    existing = session.execute(
                        select(Vacancy).where(
                            Vacancy.source_id == source_id,
                            Vacancy.source_row_hash == row_hash
                        )
                    ).scalar_one_or_none()
                
                # If not found, try by city+address+position (for legacy data migration)
                if not existing:
                    existing = session.execute(
                        select(Vacancy).where(
                            Vacancy.city == city,
                            Vacancy.address == address,
                            Vacancy.position == position
                        )
                    ).scalar_one_or_none()
                
                if existing:
                    # Update source_id and hash for future syncs (migration)
                    if source_id and (existing.source_id != source_id or existing.source_row_hash != row_hash):
                        existing.source_id = source_id
                        existing.source_row_hash = row_hash
                    
                    # Handle relevance changes only - don't reset status of published vacancies!
                    if not is_relevant and existing.status != VacancyStatus.ARCHIVED:
                        logger.info(f"Archiving vacancy {existing.id} (not relevant)")
                        existing.status = VacancyStatus.ARCHIVED
                        updated += 1
                    elif is_relevant and existing.status == VacancyStatus.ARCHIVED:
                        # Restore from archive - try to restore previous state based on fields
                        new_status = VacancyStatus.PENDING
                        if existing.avito_ad_id or existing.status == VacancyStatus.PUBLISHED: # Keep PUBLISHED if somehow it was set
                            new_status = VacancyStatus.PUBLISHED
                        elif existing.xml_exported:
                             new_status = VacancyStatus.PUBLISHED # Assume published if exported
                        elif existing.image_url:
                            new_status = VacancyStatus.IMAGE_GENERATED
                        elif existing.title and existing.description:
                            new_status = VacancyStatus.TEXT_GENERATED
                        
                        logger.info(f"Restoring vacancy {existing.id} from archive to {new_status}")
                        existing.status = new_status
                        updated += 1
                    
                    skipped += 1
                    continue
                
                # Skip non-relevant for new entries
                if not is_relevant:
                    skipped += 1
                    continue
                
                vacancy_id = generate_vacancy_id(city)
                
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
                    source_id=source_id,
                    source_row_hash=row_hash,
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
        "updated": updated,
        "errors": errors,
        "total": len(df),
        "batch_id": batch_id,
    }


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE SYNC TASKS
# ═══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def sync_source(self, source_id: str) -> dict:
    """
    Synchronize vacancies with a saved source.
    - Import new vacancies
    - Archive vacancies that are no longer in source
    - Update relevance status
    """
    from services.shared.import_sources import get_source, update_source
    
    logger.info(f"Starting sync for source: {source_id}")
    
    try:
        source = get_source(source_id)
        if not source:
            raise ValueError(f"Source not found: {source_id}")
        
        if not settings.google_credentials_json:
            raise ValueError("GOOGLE_CREDENTIALS_JSON not configured")
        
        # Fetch data from source
        gs_service = GoogleSheetsService(settings.google_credentials_json)
        data = gs_service.get_sheet_data(source.url, source.sheet_name)
        
        logger.info(f"Fetched {len(data)} rows from source: {source.name}")
        
        df = pd.DataFrame(data)
        
        # Collect all hashes from source
        source_hashes: Set[str] = set()
        for _, row in df.iterrows():
            city = str(row.get("Город", row.get("city", ""))).strip()
            address = str(row.get("Адрес", row.get("address", ""))).strip()
            position = str(row.get("Должность", row.get("position", ""))).strip()
            if city and position:
                row_hash = hashlib.md5(f"{city}|{address}|{position}".encode()).hexdigest()
                source_hashes.add(row_hash)
        
        # Archive vacancies not in source anymore
        archived_count = 0
        with Session(sync_engine) as session:
            db_vacancies = session.execute(
                select(Vacancy).where(
                    Vacancy.source_id == source_id,
                    Vacancy.status != VacancyStatus.ARCHIVED
                )
            ).scalars().all()
            
            for v in db_vacancies:
                if v.source_row_hash and v.source_row_hash not in source_hashes:
                    v.status = VacancyStatus.ARCHIVED
                    archived_count += 1
            
            session.commit()
        
        logger.info(f"Archived {archived_count} vacancies not in source")
        
        # Process new/updated data
        from services.shared.models.import_batch import ImportSource as ImportSourceEnum
        result = _process_dataframe(
            df, 
            ImportSourceEnum.GOOGLE_SHEETS, 
            source.url, 
            column_mapping=source.column_mapping or None,
            source_id=source_id
        )
        result["archived"] = archived_count
        
        # Update source status
        update_source(source_id, {
            "last_imported_at": datetime.utcnow().isoformat(),
            "last_sync_status": "success",
            "last_sync_error": None
        })
        
        logger.info(f"Sync completed for {source.name}: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Sync failed for source {source_id}: {e}")
        
        # Update source with error
        try:
            from services.shared.import_sources import update_source
            update_source(source_id, {
                "last_sync_status": "error",
                "last_sync_error": str(e)
            })
        except:
            pass
        
        self.retry(exc=e)


@celery_app.task
def sync_all_active_sources() -> dict:
    """
    Sync sources based on their individual schedule.
    Called by Celery Beat every hour.
    Checks if current time matches source's schedule.
    """
    from services.shared.import_sources import get_all_sources
    
    logger.info("Checking scheduled sync for all sources")
    
    # Get current time in Moscow timezone
    from datetime import timezone
    import pytz
    moscow_tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(moscow_tz)
    current_hour = now.hour
    current_weekday = now.isoweekday()  # 1=Monday, 7=Sunday
    
    sources = get_all_sources()
    triggered = 0
    skipped = 0
    
    for source in sources:
        if not source.sync_enabled or not source.is_active:
            continue
        
        should_sync = False
        
        # Check schedule
        if source.sync_schedule_type == "daily":
            # Daily: run at specified hour
            if current_hour == source.sync_hour:
                should_sync = True
        elif source.sync_schedule_type == "weekly":
            # Weekly: run at specified hour on specified days
            if current_hour == source.sync_hour and current_weekday in source.sync_days:
                should_sync = True
        
        if should_sync:
            sync_source.delay(source.id)
            triggered += 1
            logger.info(f"Triggered sync for source: {source.name}")
        else:
            skipped += 1
    
    logger.info(f"Sync check complete: {triggered} triggered, {skipped} skipped")
    return {"triggered": triggered, "skipped": skipped, "total_sources": len(sources)}


"""
AdsGen 2.0 - Import Sources Module
Manage multiple Google Sheets data sources in Redis.
"""

import json
import logging
import uuid
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

import redis
from services.shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Redis key prefix for import sources
IMPORT_SOURCES_KEY = "adsgen:import_sources"


class ImportSource(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    url: str
    sheet_name: str
    column_mapping: Dict[str, str] = Field(default_factory=dict)
    is_active: bool = True
    last_imported_at: Optional[str] = None
    
    # Sync settings
    sync_enabled: bool = False  # Включена ли автосинхронизация
    sync_schedule_type: str = "daily"  # "daily" или "weekly"
    sync_hour: int = 9  # Час запуска (0-23)
    sync_days: List[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])  # Дни недели (1=Пн, 7=Вс)
    last_sync_status: Optional[str] = None  # "success" / "error"
    last_sync_error: Optional[str] = None  # Сообщение об ошибке
    
    class Config:
        from_attributes = True


def _get_redis_client() -> redis.Redis:
    """Get Redis client."""
    return redis.from_url(settings.redis_url)


def get_all_sources() -> List[ImportSource]:
    """Get all saved import sources."""
    try:
        r = _get_redis_client()
        raw_data = r.hgetall(IMPORT_SOURCES_KEY)
        
        sources = []
        for _, data in raw_data.items():
            try:
                source_dict = json.loads(data)
                sources.append(ImportSource(**source_dict))
            except Exception as e:
                logger.error(f"Failed to parse source data: {e}")
                
        # Sort by name
        return sorted(sources, key=lambda s: s.name)
        
    except Exception as e:
        logger.error(f"Failed to get import sources: {e}")
        return []


def get_source(source_id: str) -> Optional[ImportSource]:
    """Get a specific import source by ID."""
    try:
        r = _get_redis_client()
        data = r.hget(IMPORT_SOURCES_KEY, source_id)
        
        if data:
            return ImportSource(**json.loads(data))
        return None
        
    except Exception as e:
        logger.error(f"Failed to get import source {source_id}: {e}")
        return None


def add_source(source_data: ImportSource) -> ImportSource:
    """Add a new import source."""
    try:
        r = _get_redis_client()
        
        # Ensure ID is set
        if not source_data.id:
            source_data.id = str(uuid.uuid4())
            
        r.hset(
            IMPORT_SOURCES_KEY, 
            source_data.id, 
            source_data.json()
        )
        logger.info(f"Added import source: {source_data.name} ({source_data.id})")
        return source_data
        
    except Exception as e:
        logger.error(f"Failed to add import source: {e}")
        raise


def update_source(source_id: str, updates: Dict) -> Optional[ImportSource]:
    """Update an existing import source."""
    try:
        current = get_source(source_id)
        if not current:
            return None
            
        # Update fields
        current_data = current.dict()
        for key, value in updates.items():
            if key in current_data:
                current_data[key] = value
                
        updated_source = ImportSource(**current_data)
        
        r = _get_redis_client()
        r.hset(
            IMPORT_SOURCES_KEY, 
            source_id, 
            updated_source.json()
        )
        logger.info(f"Updated import source: {updated_source.name} ({source_id})")
        return updated_source
        
    except Exception as e:
        logger.error(f"Failed to update import source: {e}")
        raise


def delete_source(source_id: str) -> bool:
    """Delete an import source."""
    try:
        r = _get_redis_client()
        result = r.hdel(IMPORT_SOURCES_KEY, source_id)
        
        if result > 0:
            logger.info(f"Deleted import source: {source_id}")
            return True
        return False
        
    except Exception as e:
        logger.error(f"Failed to delete import source: {e}")
        raise

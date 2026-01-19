"""
AdsGen 2.0 - Vacancy Schemas
Pydantic schemas for API request/response validation
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from ..models.vacancy import VacancyStatus


# ═══════════════════════════════════════════════════════════════════════════
# REQUEST SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════

class VacancyCreate(BaseModel):
    """Schema for creating a new vacancy (from import)."""
    id: str = Field(..., description="Unique ID (e.g., M123456789)")
    city: str = Field(..., max_length=100)
    address: str = Field(..., max_length=500)
    position: str = Field(..., max_length=200)
    profession: str = Field(..., max_length=200)
    schedule: Optional[str] = None
    level: Optional[str] = None
    store_type: Optional[str] = None
    service: Optional[str] = None
    notes: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None


class VacancyUpdate(BaseModel):
    """Schema for updating vacancy fields."""
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    status: Optional[VacancyStatus] = None
    error_message: Optional[str] = None
    avito_ad_id: Optional[str] = None


class TextGenerationRequest(BaseModel):
    """Request to generate text content for a vacancy."""
    vacancy_id: str


class ImageGenerationRequest(BaseModel):
    """Request to generate image for a vacancy."""
    vacancy_id: str
    gender: Optional[str] = None  # "man" or "woman"
    age: Optional[int] = Field(None, ge=18, le=65)


class ValidationRequest(BaseModel):
    """Request to validate vacancy content."""
    vacancy_id: str


class PublishRequest(BaseModel):
    """Request to publish vacancy to Avito."""
    vacancy_id: str
    export_xml: bool = True
    publish_api: bool = False


# ═══════════════════════════════════════════════════════════════════════════
# RESPONSE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════

class VacancyResponse(BaseModel):
    """Full vacancy response."""
    id: str
    city: str
    address: str
    position: str
    profession: str
    schedule: Optional[str]
    level: Optional[str]
    store_type: Optional[str]
    service: Optional[str]
    notes: Optional[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    title: Optional[str]
    description: Optional[str]
    image_url: Optional[str]
    status: VacancyStatus
    error_message: Optional[str]
    avito_ad_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VacancyListResponse(BaseModel):
    """Paginated list of vacancies."""
    items: list[VacancyResponse]
    total: int
    page: int
    per_page: int


class TaskResponse(BaseModel):
    """Response for async task submission."""
    task_id: str
    status: str
    message: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    database: str
    redis: str
    comfyui: Optional[str] = None

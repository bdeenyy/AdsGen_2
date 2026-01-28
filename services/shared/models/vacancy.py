"""
AdsGen 2.0 - Vacancy Model
Core SQLAlchemy model for vacancy/job advertisements
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class VacancyStatus(str, enum.Enum):
    """Status of vacancy processing pipeline."""
    PENDING = "PENDING"
    TEXT_GENERATING = "TEXT_GENERATING"
    TEXT_GENERATED = "TEXT_GENERATED"
    IMAGE_GENERATING = "IMAGE_GENERATING"
    IMAGE_GENERATED = "IMAGE_GENERATED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"  # Неактуальная вакансия (удалена из источника)
    ERROR = "ERROR"


class Vacancy(Base):
    """
    Vacancy model representing a job advertisement.
    Maps to the 'vacancies' table in PostgreSQL.
    """
    __tablename__ = "vacancies"

    # Primary key
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    
    # Source data (from import)
    city: Mapped[str] = mapped_column(String(100), index=True)
    address: Mapped[str] = mapped_column(String(500))
    position: Mapped[str] = mapped_column(String(200))  # Original position name
    profession: Mapped[str] = mapped_column(String(200), index=True)  # Mapped Avito profession
    schedule: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # ЧТС уровень
    store_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # ГМ/МФ
    service: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)  # Услуга
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Примечания
    
    # Deduplication fields
    source_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)  # ImportSource.id
    source_row_hash: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)  # MD5 hash
    
    # Salary
    salary_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Generated content
    title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Avito-specific fields
    manager_name: Mapped[str] = mapped_column(String(100), default="Анастасия")
    manager_phone: Mapped[str] = mapped_column(String(20), default="79082348946")
    company_name: Mapped[str] = mapped_column(String(200), default="Проектстрой-8")
    company_email: Mapped[str] = mapped_column(String(200), default="projectstroy-8@mail.ru")
    
    # Processing status
    status: Mapped[VacancyStatus] = mapped_column(
        Enum(VacancyStatus),
        default=VacancyStatus.PENDING,
        index=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Publishing
    avito_ad_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    xml_exported: Mapped[bool] = mapped_column(default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    
    def __repr__(self) -> str:
        return f"<Vacancy {self.id}: {self.profession} @ {self.city}>"

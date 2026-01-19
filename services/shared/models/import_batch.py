"""
AdsGen 2.0 - Import Batch Model
Tracks import operations and their status
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ImportSource(str, enum.Enum):
    """Source type for import."""
    CSV = "csv"
    EXCEL = "excel"
    GOOGLE_SHEETS = "google_sheets"


class ImportStatus(str, enum.Enum):
    """Status of import batch."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImportBatch(Base):
    """
    Import batch model for tracking import operations.
    """
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Source info
    source_type: Mapped[ImportSource] = mapped_column(Enum(ImportSource))
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # For Google Sheets
    filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # For CSV/Excel
    
    # Processing stats
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    
    # Status
    status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus),
        default=ImportStatus.PENDING
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    def __repr__(self) -> str:
        return f"<ImportBatch {self.id}: {self.source_type} - {self.status}>"

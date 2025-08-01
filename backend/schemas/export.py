"""Export schemas for request/response validation."""

from typing import List, Optional, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field
from enum import Enum


class ExportFormat(str, Enum):
    """Supported export formats."""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"
    PDF = "pdf"
    ZIP = "zip"


class ExportConfig(BaseModel):
    """Export configuration."""
    entity_type: str = Field(..., description="Type of entity to export")
    format: ExportFormat = Field(..., description="Export format")
    fields: Optional[List[str]] = Field(None, description="Fields to include")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters to apply")
    date_from: Optional[datetime] = Field(None, description="Start date filter")
    date_to: Optional[datetime] = Field(None, description="End date filter")
    include_related: bool = Field(False, description="Include related data")
    compress: bool = Field(False, description="Compress output")


class ExportResult(BaseModel):
    """Export result."""
    filename: str
    content: bytes
    mime_type: str
    size: int
    record_count: int


class ExportRequest(BaseModel):
    """Export request."""
    entity_type: str = Field(..., description="Type of entity to export")
    format: ExportFormat = Field(ExportFormat.CSV, description="Export format")
    fields: Optional[List[str]] = Field(None, description="Fields to include")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters to apply")
    date_from: Optional[date] = Field(None, description="Start date filter")
    date_to: Optional[date] = Field(None, description="End date filter")
    include_related: bool = Field(False, description="Include related data")
    email_delivery: bool = Field(False, description="Email the export file")
    schedule: Optional[str] = Field(None, description="Cron schedule for recurring exports")


class ExportResponse(BaseModel):
    """Export response."""
    export_id: str
    status: str
    filename: Optional[str] = None
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    record_count: Optional[int] = None
    created_at: datetime


class ExportProgress(BaseModel):
    """Export progress tracking."""
    export_id: str
    status: str
    current: int
    total: int
    percentage: float
    message: Optional[str] = None


class ScheduledExport(BaseModel):
    """Scheduled export configuration."""
    id: str
    name: str
    entity_type: str
    format: ExportFormat
    schedule: str  # Cron expression
    email_recipients: List[str]
    filters: Optional[Dict[str, Any]] = None
    is_active: bool
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime
    created_by: str


class ExportTemplate(BaseModel):
    """Export template for reusable configurations."""
    id: str
    name: str
    description: Optional[str] = None
    entity_type: str
    format: ExportFormat
    fields: List[str]
    filters: Optional[Dict[str, Any]] = None
    is_public: bool
    created_by: str
    created_at: datetime
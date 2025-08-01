"""Import schemas for request/response validation."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class ImportFormat(str, Enum):
    """Supported import formats."""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"


class ImportConfig(BaseModel):
    """Import configuration."""
    entity_type: str = Field(..., description="Type of entity to import")
    format: ImportFormat = Field(..., description="Import format")
    field_mapping: Optional[Dict[str, str]] = Field(None, description="Field mapping")
    sheet_name: Optional[str] = Field(None, description="Excel sheet name")
    update_existing: bool = Field(False, description="Update existing records")
    continue_on_error: bool = Field(True, description="Continue on error")
    validate_only: bool = Field(False, description="Only validate, don't import")
    task_id: Optional[str] = Field(None, description="Background task ID")


class ValidationError(Exception):
    """Validation error with details."""
    def __init__(self, field: str, value: Any, message: str):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"{field}: {message}")


class ImportError(BaseModel):
    """Import error details."""
    row_number: int
    field: Optional[str] = None
    value: str
    error: str


class ImportResult(BaseModel):
    """Import result."""
    total_records: int
    successful_records: int
    failed_records: int
    errors: List[ImportError]
    created_ids: Optional[List[str]] = None
    preview_data: Optional[List[Dict[str, Any]]] = None


class ImportProgress(BaseModel):
    """Import progress tracking."""
    current: int
    total: int
    percentage: float
    status: str = "processing"
    message: Optional[str] = None


class FieldMapping(BaseModel):
    """Field mapping configuration."""
    source_field: str
    target_field: str
    transform: Optional[str] = None  # Transform function name
    default_value: Optional[Any] = None


class ImportTemplate(BaseModel):
    """Import template for reusable configurations."""
    id: str
    name: str
    description: Optional[str] = None
    entity_type: str
    format: ImportFormat
    field_mappings: List[FieldMapping]
    sample_file_url: Optional[str] = None
    created_by: str
    created_at: datetime


class ImportRequest(BaseModel):
    """Import request."""
    entity_type: str = Field(..., description="Type of entity to import")
    format: ImportFormat = Field(..., description="Import format")
    field_mapping: Optional[Dict[str, str]] = Field(None, description="Field mapping")
    update_existing: bool = Field(False, description="Update existing records")
    continue_on_error: bool = Field(True, description="Continue on error")
    validate_only: bool = Field(False, description="Only validate, don't import")
    send_notifications: bool = Field(True, description="Send import notifications")


class ImportResponse(BaseModel):
    """Import response."""
    import_id: str
    status: str
    total_records: Optional[int] = None
    successful_records: Optional[int] = None
    failed_records: Optional[int] = None
    errors_file_url: Optional[str] = None
    created_at: datetime


class BulkImportJob(BaseModel):
    """Bulk import job details."""
    id: str
    entity_type: str
    filename: str
    status: str
    total_records: int
    processed_records: int
    successful_records: int
    failed_records: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: str
    error_details_url: Optional[str] = None
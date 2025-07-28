"""
Pydantic schemas for reporting module.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

from .models import ReportStatus, DeliveryMethod


# Widget Schemas
class ReportWidgetConfig(BaseModel):
    """Configuration for a report widget."""
    type: str  # metric, chart, table, text, comparison
    title: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    position: Optional[int] = None
    size: str = "medium"  # small, medium, large, full


# Template Schemas
class ReportTemplateBase(BaseModel):
    """Base schema for report templates."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    report_type: str  # revenue, engagement, comprehensive, custom
    layout: Dict[str, Any] = Field(default_factory=dict)
    filters: Dict[str, Any] = Field(default_factory=dict)
    is_public: bool = False


class ReportTemplateCreate(ReportTemplateBase):
    """Schema for creating a report template."""
    widgets: List[ReportWidgetConfig] = Field(default_factory=list)


class ReportTemplateUpdate(BaseModel):
    """Schema for updating a report template."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    layout: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None
    widgets: Optional[List[ReportWidgetConfig]] = None


class ReportTemplateResponse(ReportTemplateBase):
    """Schema for report template responses."""
    id: UUID
    agency_id: UUID
    created_by_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    widget_count: Optional[int] = 0
    
    class Config:
        from_attributes = True


# Report Generation Schemas
class ReportGenerateRequest(BaseModel):
    """Request to generate a report."""
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    model_id: Optional[UUID] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    format: str = "json"  # json, pdf, excel, csv


class GeneratedReportResponse(BaseModel):
    """Response for a generated report."""
    id: UUID
    template_id: Optional[UUID]
    agency_id: UUID
    generated_by_id: Optional[UUID]
    status: ReportStatus
    parameters: Dict[str, Any]
    report_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    file_url: Optional[str] = None
    file_format: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Schedule Schemas
class ScheduleParameters(BaseModel):
    """Parameters for scheduled report generation."""
    date_range_type: str = "last_30_days"  # last_7_days, last_30_days, last_month, custom
    custom_date_from: Optional[datetime] = None
    custom_date_to: Optional[datetime] = None
    model_id: Optional[UUID] = None
    filters: Dict[str, Any] = Field(default_factory=dict)


class DeliveryConfig(BaseModel):
    """Configuration for report delivery."""
    recipients: Optional[List[str]] = None  # Email addresses
    webhook_url: Optional[str] = None
    webhook_headers: Optional[Dict[str, str]] = None
    s3_bucket: Optional[str] = None
    s3_path: Optional[str] = None
    sftp_host: Optional[str] = None
    sftp_path: Optional[str] = None
    sftp_username: Optional[str] = None


class ReportScheduleBase(BaseModel):
    """Base schema for report schedules."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    template_id: UUID
    schedule_type: str  # daily, weekly, monthly, cron
    cron_expression: Optional[str] = None
    timezone: str = "UTC"
    parameters: ScheduleParameters = Field(default_factory=ScheduleParameters)
    delivery_method: DeliveryMethod = DeliveryMethod.EMAIL
    delivery_config: DeliveryConfig = Field(default_factory=DeliveryConfig)
    is_active: bool = True
    
    @validator('cron_expression')
    def validate_cron(cls, v, values):
        if values.get('schedule_type') == 'cron' and not v:
            raise ValueError('Cron expression required for cron schedule type')
        return v


class ReportScheduleCreate(ReportScheduleBase):
    """Schema for creating a report schedule."""
    pass


class ReportScheduleUpdate(BaseModel):
    """Schema for updating a report schedule."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    schedule_type: Optional[str] = None
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    parameters: Optional[ScheduleParameters] = None
    delivery_method: Optional[DeliveryMethod] = None
    delivery_config: Optional[DeliveryConfig] = None
    is_active: Optional[bool] = None


class ReportScheduleResponse(ReportScheduleBase):
    """Schema for report schedule responses."""
    id: UUID
    agency_id: UUID
    created_by_id: Optional[UUID]
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    success_count: int
    failure_count: int
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Export Schemas
class ExportRequest(BaseModel):
    """Request to export analytics data."""
    export_type: str  # revenue, engagement, fans, content, messages, financial, comprehensive
    format: str  # csv, excel, pdf, json
    model_id: Optional[UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    filters: Optional[Dict[str, Any]] = None


class ExportResponse(BaseModel):
    """Response for data export."""
    export_id: UUID
    status: str
    format: str
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
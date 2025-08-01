"""Schemas for schedule management."""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class TaskType(str, Enum):
    """Scheduled task types."""
    REPORT_GENERATION = "report_generation"
    DATA_SYNC = "data_sync"
    CLEANUP = "cleanup"
    NOTIFICATION = "notification"
    BACKUP = "backup"
    CUSTOM = "custom"


class CronValidationRequest(BaseModel):
    """Request for cron expression validation."""
    expression: str = Field(..., description="Cron expression or predefined schedule name")
    timezone: Optional[str] = Field("UTC", description="Timezone for schedule")
    include_stats: bool = Field(False, description="Include frequency statistics")
    stats_period_days: Optional[int] = Field(30, description="Period for frequency statistics")


class FrequencyStats(BaseModel):
    """Frequency statistics for a cron expression."""
    total_runs: int
    daily_average: float
    weekly_average: float
    runs_per_day: Dict[str, int]
    min_interval_minutes: Optional[float]
    max_interval_minutes: Optional[float]
    avg_interval_minutes: Optional[float]


class CronField(BaseModel):
    """Individual cron field information."""
    value: str
    description: str


class CronExpressionInfo(BaseModel):
    """Detailed cron expression information."""
    valid: bool
    expression: str
    cron: str
    schedule_name: Optional[str]
    description: str
    next_runs: List[str]
    timezone: str
    fields: Dict[str, CronField]
    frequency_stats: Optional[FrequencyStats] = None


class CronValidationResponse(BaseModel):
    """Response for cron expression validation."""
    valid: bool
    expression: str
    cron: Optional[str] = None
    schedule_name: Optional[str] = None
    description: Optional[str] = None
    next_runs: Optional[List[str]] = None
    timezone: Optional[str] = None
    fields: Optional[Dict[str, Dict[str, str]]] = None
    frequency_stats: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ScheduleCreateRequest(BaseModel):
    """Request to create a scheduled task."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    task_type: TaskType
    cron_expression: str = Field(..., description="Cron expression or predefined schedule")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_active: bool = Field(True)


class ScheduleUpdateRequest(BaseModel):
    """Request to update a scheduled task."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    cron_expression: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ScheduleResponse(BaseModel):
    """Response for scheduled task."""
    id: str
    name: str
    description: Optional[str]
    task_type: TaskType
    cron_expression: str
    cron_info: CronExpressionInfo
    parameters: Dict[str, Any]
    is_active: bool
    last_run: Optional[datetime]
    next_run: Optional[str]
    created_at: datetime
    updated_at: datetime


class ScheduleListResponse(BaseModel):
    """Response for list of scheduled tasks."""
    tasks: List[ScheduleResponse]


class PredefinedSchedule(BaseModel):
    """Predefined schedule option."""
    name: str
    cron: str
    description: str


class ScheduledTaskExecution(BaseModel):
    """Scheduled task execution record."""
    id: str
    task_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: str  # pending, running, completed, failed
    result: Optional[Dict[str, Any]]
    error: Optional[str]


class TaskRunRequest(BaseModel):
    """Request to run a task immediately."""
    override_parameters: Optional[Dict[str, Any]] = None
"""Task management schemas."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum

from models.task_result import TaskStatus


class TaskCreateRequest(BaseModel):
    """Base request for creating tasks."""
    params: Dict[str, Any] = Field(default_factory=dict)


class ExportRequest(BaseModel):
    """Request for data export tasks."""
    include_media: bool = False
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    format: str = Field("json", pattern="^(json|csv|excel)$")


class TaskResponse(BaseModel):
    """Task response with current status."""
    task_id: str
    task_name: str
    status: TaskStatus
    user_id: UUID
    agency_id: Optional[UUID]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result: Optional[Any] = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    progress: Optional[int] = None
    params: Optional[Dict[str, Any]] = None
    
    class Config:
        orm_mode = True
    
    @classmethod
    def from_orm(cls, task_result, celery_info: Optional[Dict[str, Any]] = None):
        """Create from ORM model with Celery info."""
        data = {
            'task_id': task_result.task_id,
            'task_name': task_result.task_name,
            'status': task_result.status,
            'user_id': task_result.user_id,
            'agency_id': task_result.agency_id,
            'created_at': task_result.created_at,
            'started_at': task_result.started_at,
            'completed_at': task_result.completed_at,
            'params': task_result.params
        }
        
        # Update with Celery info if available
        if celery_info:
            data['status'] = TaskStatus(celery_info['status'])
            data['result'] = celery_info.get('result')
            data['error'] = celery_info.get('traceback')
            
            # Extract progress from result if available
            if isinstance(celery_info.get('result'), dict):
                data['progress'] = celery_info['result'].get('progress')
        
        return cls(**data)


class TaskListResponse(BaseModel):
    """List of tasks with pagination."""
    items: List[TaskResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class TaskStatsResponse(BaseModel):
    """Task statistics response."""
    time_range: str
    total_tasks: int
    status_breakdown: Dict[TaskStatus, int]
    type_breakdown: Dict[str, int]
    average_duration_seconds: float
    success_rate: float
    
    class Config:
        use_enum_values = True


class TaskQueueInfo(BaseModel):
    """Information about task queues."""
    queue_name: str
    pending_tasks: int
    active_tasks: int
    reserved_tasks: int
    
    
class WorkerInfo(BaseModel):
    """Information about Celery workers."""
    worker_name: str
    status: str
    active_tasks: int
    processed_tasks: int
    pool_size: int
    uptime_seconds: Optional[int]


class ScheduledTaskInfo(BaseModel):
    """Information about scheduled periodic tasks."""
    name: str
    task: str
    schedule: str
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    enabled: bool
    options: Dict[str, Any] = Field(default_factory=dict)
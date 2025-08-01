"""Schedule management API endpoints."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from schemas.pagination import PaginatedResponse
from utils.pagination import paginate_params, PaginationParams

from core.database import get_db
from core.auth import get_current_user
from core.logger import get_logger
from models.user import User, UserRole
from services.cron_parser import get_cron_parser, get_schedule_manager
from schemas.schedule import (
    CronValidationRequest,
    CronValidationResponse,
    ScheduleCreateRequest,
    ScheduleUpdateRequest,
    ScheduleResponse,
    ScheduleListResponse,
    CronExpressionInfo
)

logger = get_logger(__name__)
router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.post("/validate-cron", response_model=CronValidationResponse)
async def validate_cron_expression(
    request: CronValidationRequest,
    current_user: User = Depends(get_current_user)
) -> CronValidationResponse:
    """
    Validate a cron expression and get next run times.
    
    Accepts both standard cron expressions and predefined schedules:
    - hourly, daily, weekly, monthly, quarterly, yearly
    - business_days, weekends, twice_daily
    - every_6_hours, every_30_minutes, every_15_minutes
    """
    cron_parser = get_cron_parser(request.timezone or 'UTC')
    result = cron_parser.parse(request.expression)
    
    if not result['valid']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cron expression: {result.get('error', 'Unknown error')}"
        )
    
    # Get frequency statistics if requested
    if request.include_stats:
        result['frequency_stats'] = cron_parser.get_frequency_stats(
            result['cron'],
            request.stats_period_days or 30
        )
    
    return CronValidationResponse(**result)


@router.get("/predefined-schedules")
async def list_predefined_schedules(
    current_user: User = Depends(get_current_user)
) -> Dict[str, List[Dict[str, str]]]:
    """List all predefined schedule options."""
    from services.cron_parser import CronParser
    
    schedules = []
    for name, cron in CronParser.PREDEFINED_SCHEDULES.items():
        schedules.append({
            'name': name,
            'cron': cron,
            'description': CronParser.SCHEDULE_DESCRIPTIONS.get(name, '')
        })
    
    return {"schedules": schedules}


@router.post("/tasks", response_model=ScheduleResponse)
async def create_scheduled_task(
    request: ScheduleCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ScheduleResponse:
    """
    Create a new scheduled task.
    
    Task types:
    - report_generation: Generate reports on schedule
    - data_sync: Sync data from external APIs
    - cleanup: Clean up old data
    - notification: Send scheduled notifications
    - backup: Perform backups
    """
    # Check permissions
    if current_user.role not in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create scheduled tasks"
        )
    
    # Validate cron expression
    cron_parser = get_cron_parser(current_user.agency.timezone if current_user.agency else 'UTC')
    is_valid, error = cron_parser.validate(request.cron_expression)
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cron expression: {error}"
        )
    
    # Create scheduled task in database
    from models.scheduled_task import ScheduledTask
    
    task = ScheduledTask(
        name=request.name,
        description=request.description,
        task_type=request.task_type,
        cron_expression=request.cron_expression,
        parameters=request.parameters,
        agency_id=current_user.agency_id,
        created_by_id=current_user.id,
        is_active=request.is_active
    )
    
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    # Parse cron info for response
    cron_info = cron_parser.parse(task.cron_expression)
    
    return ScheduleResponse(
        id=str(task.id),
        name=task.name,
        description=task.description,
        task_type=task.task_type,
        cron_expression=task.cron_expression,
        cron_info=CronExpressionInfo(**cron_info),
        parameters=task.parameters,
        is_active=task.is_active,
        last_run=task.last_run,
        next_run=cron_info['next_runs'][0] if cron_info.get('next_runs') else None,
        created_at=task.created_at,
        updated_at=task.updated_at
    )


@router.get("/tasks", response_model=ScheduleListResponse)
async def list_scheduled_tasks(
    task_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ScheduleListResponse:
    """List all scheduled tasks for the agency."""
    from sqlalchemy import select
    from models.scheduled_task import ScheduledTask
    
    query = select(ScheduledTask).where(
        ScheduledTask.agency_id == current_user.agency_id
    )
    
    if task_type:
        query = query.where(ScheduledTask.task_type == task_type)
    
    if is_active is not None:
        query = query.where(ScheduledTask.is_active == is_active)
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    # Get cron parser
    cron_parser = get_cron_parser(current_user.agency.timezone if current_user.agency else 'UTC')
    
    # Build response
    task_responses = []
    for task in tasks:
        cron_info = cron_parser.parse(task.cron_expression)
        
        task_responses.append(ScheduleResponse(
            id=str(task.id),
            name=task.name,
            description=task.description,
            task_type=task.task_type,
            cron_expression=task.cron_expression,
            cron_info=CronExpressionInfo(**cron_info),
            parameters=task.parameters,
            is_active=task.is_active,
            last_run=task.last_run,
            next_run=cron_info['next_runs'][0] if cron_info.get('next_runs') else None,
            created_at=task.created_at,
            updated_at=task.updated_at
        ))
    
    return ScheduleListResponse(tasks=task_responses)


@router.get("/tasks/{task_id}", response_model=ScheduleResponse)
async def get_scheduled_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ScheduleResponse:
    """Get details of a specific scheduled task."""
    from sqlalchemy import select
    from models.scheduled_task import ScheduledTask
    
    result = await db.execute(
        select(ScheduledTask).where(
            ScheduledTask.id == task_id,
            ScheduledTask.agency_id == current_user.agency_id
        )
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled task not found"
        )
    
    # Get cron parser
    cron_parser = get_cron_parser(current_user.agency.timezone if current_user.agency else 'UTC')
    cron_info = cron_parser.parse(task.cron_expression)
    
    # Get frequency stats
    frequency_stats = cron_parser.get_frequency_stats(task.cron_expression)
    cron_info['frequency_stats'] = frequency_stats
    
    return ScheduleResponse(
        id=str(task.id),
        name=task.name,
        description=task.description,
        task_type=task.task_type,
        cron_expression=task.cron_expression,
        cron_info=CronExpressionInfo(**cron_info),
        parameters=task.parameters,
        is_active=task.is_active,
        last_run=task.last_run,
        next_run=cron_info['next_runs'][0] if cron_info.get('next_runs') else None,
        created_at=task.created_at,
        updated_at=task.updated_at
    )


@router.put("/tasks/{task_id}", response_model=ScheduleResponse)
async def update_scheduled_task(
    task_id: str,
    request: ScheduleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ScheduleResponse:
    """Update a scheduled task."""
    # Check permissions
    if current_user.role not in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update scheduled tasks"
        )
    
    from sqlalchemy import select
    from models.scheduled_task import ScheduledTask
    
    result = await db.execute(
        select(ScheduledTask).where(
            ScheduledTask.id == task_id,
            ScheduledTask.agency_id == current_user.agency_id
        )
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled task not found"
        )
    
    # Update fields
    if request.name is not None:
        task.name = request.name
    
    if request.description is not None:
        task.description = request.description
    
    if request.cron_expression is not None:
        # Validate new cron expression
        cron_parser = get_cron_parser(current_user.agency.timezone if current_user.agency else 'UTC')
        is_valid, error = cron_parser.validate(request.cron_expression)
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid cron expression: {error}"
            )
        
        task.cron_expression = request.cron_expression
    
    if request.parameters is not None:
        task.parameters = request.parameters
    
    if request.is_active is not None:
        task.is_active = request.is_active
    
    task.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(task)
    
    # Get updated cron info
    cron_parser = get_cron_parser(current_user.agency.timezone if current_user.agency else 'UTC')
    cron_info = cron_parser.parse(task.cron_expression)
    
    return ScheduleResponse(
        id=str(task.id),
        name=task.name,
        description=task.description,
        task_type=task.task_type,
        cron_expression=task.cron_expression,
        cron_info=CronExpressionInfo(**cron_info),
        parameters=task.parameters,
        is_active=task.is_active,
        last_run=task.last_run,
        next_run=cron_info['next_runs'][0] if cron_info.get('next_runs') else None,
        created_at=task.created_at,
        updated_at=task.updated_at
    )


@router.delete("/tasks/{task_id}")
async def delete_scheduled_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """Delete a scheduled task."""
    # Check permissions
    if current_user.role not in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete scheduled tasks"
        )
    
    from sqlalchemy import select
    from models.scheduled_task import ScheduledTask
    
    result = await db.execute(
        select(ScheduledTask).where(
            ScheduledTask.id == task_id,
            ScheduledTask.agency_id == current_user.agency_id
        )
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled task not found"
        )
    
    await db.delete(task)
    await db.commit()
    
    return {"message": f"Scheduled task '{task.name}' deleted successfully"}


@router.post("/tasks/{task_id}/run")
async def run_scheduled_task_now(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Manually trigger a scheduled task to run immediately."""
    from sqlalchemy import select
    from models.scheduled_task import ScheduledTask
    from tasks.scheduled_tasks import execute_scheduled_task
    
    result = await db.execute(
        select(ScheduledTask).where(
            ScheduledTask.id == task_id,
            ScheduledTask.agency_id == current_user.agency_id
        )
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled task not found"
        )
    
    if not task.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot run inactive task"
        )
    
    # Queue task for immediate execution
    task_result = execute_scheduled_task.delay(str(task.id))
    
    return {
        "message": f"Task '{task.name}' queued for immediate execution",
        "task_id": str(task.id),
        "job_id": task_result.id
    }


@router.get("/next-runs")
async def get_upcoming_runs(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, List[Dict[str, Any]]]:
    """Get all scheduled tasks that will run in the next N hours."""
    from sqlalchemy import select
    from models.scheduled_task import ScheduledTask
    
    result = await db.execute(
        select(ScheduledTask).where(
            ScheduledTask.agency_id == current_user.agency_id,
            ScheduledTask.is_active == True
        )
    )
    tasks = result.scalars().all()
    
    # Get cron parser
    cron_parser = get_cron_parser(current_user.agency.timezone if current_user.agency else 'UTC')
    
    # Calculate upcoming runs
    upcoming_runs = []
    cutoff_time = datetime.now() + timedelta(hours=hours)
    
    for task in tasks:
        next_runs = cron_parser.get_next_runs(task.cron_expression, count=10)
        
        for run_time_str in next_runs:
            run_time = datetime.fromisoformat(run_time_str.replace('Z', '+00:00'))
            
            if run_time <= cutoff_time:
                upcoming_runs.append({
                    'task_id': str(task.id),
                    'task_name': task.name,
                    'task_type': task.task_type,
                    'run_time': run_time_str
                })
            else:
                break  # No need to check further runs
    
    # Sort by run time
    upcoming_runs.sort(key=lambda x: x['run_time'])
    
    return {
        "period_hours": hours,
        "total_runs": len(upcoming_runs),
        "upcoming_runs": upcoming_runs
    }
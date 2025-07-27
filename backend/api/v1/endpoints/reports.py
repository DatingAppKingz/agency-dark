"""
Advanced reporting system API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from pydantic import BaseModel, Field

from core.dependencies import get_db, get_current_user
from core.domain.models import User, UserRole
from core.reporting.models import (
    Report, ReportExecution, ReportSchedule, ReportTemplate,
    ReportType, ReportFormat, ReportStatus
)
from core.reporting.report_builder import report_builder
from core.reporting.exporters import export_manager
from core.domain.schemas import BaseResponse

router = APIRouter(prefix="/reports", tags=["reports"])


# Schemas
class ReportCreate(BaseModel):
    """Create a new report."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    report_type: ReportType
    query_config: Dict[str, Any] = Field(..., description="Query configuration")
    filters: Optional[Dict[str, Any]] = None
    columns: Optional[List[str]] = None
    grouping: Optional[List[str]] = None
    sorting: Optional[Dict[str, str]] = None
    aggregations: Optional[Dict[str, Any]] = None
    chart_config: Optional[Dict[str, Any]] = None
    cache_duration_minutes: int = Field(60, ge=0, le=1440)


class ReportUpdate(BaseModel):
    """Update report configuration."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    columns: Optional[List[str]] = None
    grouping: Optional[List[str]] = None
    sorting: Optional[Dict[str, str]] = None
    aggregations: Optional[Dict[str, Any]] = None
    chart_config: Optional[Dict[str, Any]] = None
    cache_duration_minutes: Optional[int] = Field(None, ge=0, le=1440)


class ReportExecute(BaseModel):
    """Execute a report."""
    format: ReportFormat = Field(ReportFormat.JSON)
    parameters: Optional[Dict[str, Any]] = None
    use_cache: bool = True


class ReportFromTemplate(BaseModel):
    """Create report from template."""
    template_id: UUID
    name: str = Field(..., min_length=1, max_length=200)
    customizations: Optional[Dict[str, Any]] = None


class ReportShare(BaseModel):
    """Share report with users."""
    user_ids: List[UUID]
    permission: str = Field("view", description="view or edit")


class ReportScheduleCreate(BaseModel):
    """Create report schedule."""
    cron_expression: str = Field(..., description="Cron expression for scheduling")
    format: ReportFormat
    delivery_method: str = Field("email", description="email, webhook, or storage")
    delivery_config: Dict[str, Any] = Field(..., description="Delivery configuration")
    parameters: Optional[Dict[str, Any]] = None
    recipient_users: Optional[List[UUID]] = None
    recipient_emails: Optional[List[str]] = None
    timezone: str = Field("UTC")


class ReportResponse(BaseModel):
    """Report response."""
    id: UUID
    name: str
    description: Optional[str]
    report_type: str
    created_by_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]
    last_run_at: Optional[datetime]
    run_count: int
    is_public: bool
    is_template: bool
    shared_with_count: int


class ReportExecutionResponse(BaseModel):
    """Report execution response."""
    id: UUID
    report_id: UUID
    status: str
    format: str
    row_count: Optional[int]
    file_size_bytes: Optional[int]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    execution_time_ms: Optional[int]
    error_message: Optional[str]
    download_url: Optional[str]


# Endpoints

@router.post("/", response_model=ReportResponse)
async def create_report(
    report: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ReportResponse:
    """Create a new custom report."""
    # Create report
    new_report = await report_builder.create_report(
        name=report.name,
        report_type=report.report_type,
        query_config=report.query_config,
        user=current_user,
        session=db,
        description=report.description,
        filters=report.filters,
        columns=report.columns,
        grouping=report.grouping,
        sorting=report.sorting,
        aggregations=report.aggregations,
        chart_config=report.chart_config
    )
    
    new_report.cache_duration_minutes = report.cache_duration_minutes
    await db.commit()
    
    return ReportResponse(
        id=new_report.id,
        name=new_report.name,
        description=new_report.description,
        report_type=new_report.report_type.value,
        created_by_id=new_report.created_by_id,
        created_at=new_report.created_at,
        updated_at=new_report.updated_at,
        last_run_at=new_report.last_run_at,
        run_count=new_report.run_count,
        is_public=new_report.is_public,
        is_template=new_report.is_template,
        shared_with_count=len(new_report.shared_with)
    )


@router.get("/", response_model=List[ReportResponse])
async def list_reports(
    report_type: Optional[ReportType] = None,
    is_template: Optional[bool] = None,
    shared_with_me: bool = False,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[ReportResponse]:
    """List available reports."""
    query = select(Report)
    
    # Base filters
    if shared_with_me:
        query = query.join(Report.shared_with).where(User.id == current_user.id)
    else:
        # Show reports from same agency or created by user
        query = query.where(
            or_(
                Report.created_by_id == current_user.id,
                Report.agency_id == current_user.agency_id,
                Report.is_public == True
            )
        )
    
    # Additional filters
    if report_type:
        query = query.where(Report.report_type == report_type)
    if is_template is not None:
        query = query.where(Report.is_template == is_template)
    
    # Order and paginate
    query = query.order_by(Report.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(query)
    reports = result.scalars().all()
    
    return [
        ReportResponse(
            id=report.id,
            name=report.name,
            description=report.description,
            report_type=report.report_type.value,
            created_by_id=report.created_by_id,
            created_at=report.created_at,
            updated_at=report.updated_at,
            last_run_at=report.last_run_at,
            run_count=report.run_count,
            is_public=report.is_public,
            is_template=report.is_template,
            shared_with_count=len(report.shared_with)
        )
        for report in reports
    ]


@router.get("/{report_id}", response_model=Dict[str, Any])
async def get_report(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get report details."""
    result = await db.execute(
        select(Report).where(Report.id == report_id)
    )
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check access
    if not await report_builder._can_access_report(report, current_user, db):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "id": report.id,
        "name": report.name,
        "description": report.description,
        "report_type": report.report_type.value,
        "query_config": report.query_config,
        "filters": report.filters,
        "columns": report.columns,
        "grouping": report.grouping,
        "sorting": report.sorting,
        "aggregations": report.aggregations,
        "chart_config": report.chart_config,
        "cache_duration_minutes": report.cache_duration_minutes,
        "created_by_id": report.created_by_id,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
        "last_run_at": report.last_run_at,
        "run_count": report.run_count,
        "is_public": report.is_public,
        "is_template": report.is_template
    }


@router.put("/{report_id}", response_model=BaseResponse)
async def update_report(
    report_id: UUID,
    update: ReportUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Update report configuration."""
    result = await db.execute(
        select(Report).where(Report.id == report_id)
    )
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check permissions
    if report.created_by_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only report owner can update")
    
    # Update fields
    if update.name is not None:
        report.name = update.name
    if update.description is not None:
        report.description = update.description
    if update.filters is not None:
        report.filters = update.filters
    if update.columns is not None:
        report.columns = update.columns
    if update.grouping is not None:
        report.grouping = update.grouping
    if update.sorting is not None:
        report.sorting = update.sorting
    if update.aggregations is not None:
        report.aggregations = update.aggregations
    if update.chart_config is not None:
        report.chart_config = update.chart_config
    if update.cache_duration_minutes is not None:
        report.cache_duration_minutes = update.cache_duration_minutes
    
    report.updated_at = datetime.utcnow()
    await db.commit()
    
    return BaseResponse(
        success=True,
        message="Report updated successfully"
    )


@router.post("/{report_id}/execute", response_model=ReportExecutionResponse)
async def execute_report(
    report_id: UUID,
    execute: ReportExecute,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ReportExecutionResponse:
    """Execute a report."""
    execution = await report_builder.execute_report(
        report_id=str(report_id),
        format=execute.format,
        user=current_user,
        session=db,
        parameters=execute.parameters,
        use_cache=execute.use_cache
    )
    
    download_url = None
    if execution.status == ReportStatus.COMPLETED and execution.file_path:
        download_url = f"/api/v1/reports/executions/{execution.id}/download"
    
    return ReportExecutionResponse(
        id=execution.id,
        report_id=execution.report_id,
        status=execution.status.value,
        format=execution.format.value,
        row_count=execution.row_count,
        file_size_bytes=execution.file_size_bytes,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        execution_time_ms=execution.execution_time_ms,
        error_message=execution.error_message,
        download_url=download_url
    )


@router.get("/{report_id}/preview")
async def preview_report(
    report_id: UUID,
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get a preview of report data."""
    result = await db.execute(
        select(Report).where(Report.id == report_id)
    )
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check access
    if not await report_builder._can_access_report(report, current_user, db):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get preview data
    df = await report_builder.get_report_data(report, None, db)
    preview_df = df.head(limit)
    
    return {
        "columns": preview_df.columns.tolist(),
        "data": preview_df.to_dict(orient='records'),
        "total_rows": len(df),
        "preview_rows": len(preview_df)
    }


@router.post("/from-template", response_model=ReportResponse)
async def create_from_template(
    template: ReportFromTemplate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ReportResponse:
    """Create a report from a template."""
    report = await report_builder.create_from_template(
        template_id=str(template.template_id),
        name=template.name,
        user=current_user,
        session=db,
        customizations=template.customizations
    )
    
    return ReportResponse(
        id=report.id,
        name=report.name,
        description=report.description,
        report_type=report.report_type.value,
        created_by_id=report.created_by_id,
        created_at=report.created_at,
        updated_at=report.updated_at,
        last_run_at=report.last_run_at,
        run_count=report.run_count,
        is_public=report.is_public,
        is_template=report.is_template,
        shared_with_count=0
    )


@router.post("/{report_id}/share", response_model=BaseResponse)
async def share_report(
    report_id: UUID,
    share: ReportShare,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Share a report with other users."""
    await report_builder.share_report(
        report_id=str(report_id),
        user_ids=[str(uid) for uid in share.user_ids],
        permission=share.permission,
        shared_by=current_user,
        session=db
    )
    
    return BaseResponse(
        success=True,
        message=f"Report shared with {len(share.user_ids)} users"
    )


@router.post("/{report_id}/schedule", response_model=Dict[str, Any])
async def schedule_report(
    report_id: UUID,
    schedule: ReportScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Schedule a report for periodic generation."""
    report_schedule = await report_builder.schedule_report(
        report_id=str(report_id),
        cron_expression=schedule.cron_expression,
        format=schedule.format,
        delivery_config=schedule.delivery_config,
        user=current_user,
        session=db,
        parameters=schedule.parameters,
        recipient_users=[str(uid) for uid in schedule.recipient_users] if schedule.recipient_users else None,
        recipient_emails=schedule.recipient_emails
    )
    
    return {
        "id": report_schedule.id,
        "report_id": report_schedule.report_id,
        "cron_expression": report_schedule.cron_expression,
        "format": report_schedule.format.value,
        "next_run_at": report_schedule.next_run_at,
        "is_active": report_schedule.is_active
    }


@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ReportExecutionResponse:
    """Get execution details."""
    result = await db.execute(
        select(ReportExecution)
        .options(selectinload(ReportExecution.report))
        .where(ReportExecution.id == execution_id)
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    # Check access
    if not await report_builder._can_access_report(execution.report, current_user, db):
        raise HTTPException(status_code=403, detail="Access denied")
    
    download_url = None
    if execution.status == ReportStatus.COMPLETED and execution.file_path:
        download_url = f"/api/v1/reports/executions/{execution.id}/download"
    
    return ReportExecutionResponse(
        id=execution.id,
        report_id=execution.report_id,
        status=execution.status.value,
        format=execution.format.value,
        row_count=execution.row_count,
        file_size_bytes=execution.file_size_bytes,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        execution_time_ms=execution.execution_time_ms,
        error_message=execution.error_message,
        download_url=download_url
    )


@router.get("/executions/{execution_id}/download")
async def download_execution(
    execution_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Download report execution output."""
    result = await db.execute(
        select(ReportExecution)
        .options(selectinload(ReportExecution.report))
        .where(ReportExecution.id == execution_id)
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    # Check access
    if not await report_builder._can_access_report(execution.report, current_user, db):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if execution.status != ReportStatus.COMPLETED or not execution.file_path:
        raise HTTPException(status_code=404, detail="Report file not available")
    
    # For now, return a placeholder response
    # In production, this would return the actual file
    return {
        "message": "File download would be implemented here",
        "file_path": execution.file_path,
        "format": execution.format.value,
        "size_bytes": execution.file_size_bytes
    }


@router.get("/templates")
async def list_templates(
    category: Optional[str] = None,
    report_type: Optional[ReportType] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """List available report templates."""
    from core.reporting.models import ReportTemplate
    
    query = select(ReportTemplate).where(ReportTemplate.is_active == True)
    
    if category:
        query = query.where(ReportTemplate.category == category)
    if report_type:
        query = query.where(ReportTemplate.report_type == report_type)
    
    result = await db.execute(query.order_by(ReportTemplate.usage_count.desc()))
    templates = result.scalars().all()
    
    return [
        {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "report_type": template.report_type.value,
            "usage_count": template.usage_count,
            "preview_image_url": template.preview_image_url,
            "customizable_fields": template.customizable_fields
        }
        for template in templates
    ]


@router.delete("/{report_id}", response_model=BaseResponse)
async def delete_report(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Delete a report."""
    result = await db.execute(
        select(Report).where(Report.id == report_id)
    )
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check permissions
    if report.created_by_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only report owner can delete")
    
    await db.delete(report)
    await db.commit()
    
    return BaseResponse(
        success=True,
        message="Report deleted successfully"
    )


@router.get("/statistics/usage")
async def get_report_statistics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get report usage statistics."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    since = datetime.utcnow() - timedelta(days=days)
    
    # Total reports
    total_result = await db.execute(
        select(func.count(Report.id))
        .where(Report.agency_id == current_user.agency_id)
    )
    total_reports = total_result.scalar() or 0
    
    # Executions in period
    exec_result = await db.execute(
        select(func.count(ReportExecution.id))
        .join(Report)
        .where(
            and_(
                Report.agency_id == current_user.agency_id,
                ReportExecution.created_at >= since
            )
        )
    )
    total_executions = exec_result.scalar() or 0
    
    # Most popular reports
    popular_result = await db.execute(
        select(
            Report.name,
            Report.report_type,
            func.count(ReportExecution.id).label("execution_count")
        )
        .join(ReportExecution)
        .where(
            and_(
                Report.agency_id == current_user.agency_id,
                ReportExecution.created_at >= since
            )
        )
        .group_by(Report.id, Report.name, Report.report_type)
        .order_by(func.count(ReportExecution.id).desc())
        .limit(10)
    )
    
    popular_reports = [
        {
            "name": row.name,
            "type": row.report_type.value,
            "executions": row.execution_count
        }
        for row in popular_result
    ]
    
    return {
        "total_reports": total_reports,
        "total_executions": total_executions,
        "popular_reports": popular_reports,
        "time_range_days": days
    }
"""Data export API endpoints."""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from core.database import get_db
from core.dependencies import get_current_active_user
from core.security_v2.authorization import check_permission
from core.redis import redis_client
from models.user import User
from services.export_service import ExportService
from schemas.export import (
    ExportRequest, ExportResponse, ExportConfig,
    ExportFormat, ExportProgress, ScheduledExport,
    ExportTemplate
)
from tasks.export_tasks import process_export_task
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("", response_model=ExportResponse)
async def create_export(
    export_request: ExportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new data export.
    
    Permissions:
    - exports:create
    """
    check_permission(current_user, "exports", "create")
    
    # Validate entity type access
    entity_permissions = {
        "users": "users:export",
        "models": "models:export",
        "transactions": "transactions:export",
        "messages": "messages:export",
        "media": "media:export",
        "analytics": "analytics:export",
    }
    
    required_permission = entity_permissions.get(export_request.entity_type)
    if required_permission:
        resource, action = required_permission.split(":")
        check_permission(current_user, resource, action)
    
    # Create export config
    config = ExportConfig(
        entity_type=export_request.entity_type,
        format=export_request.format,
        fields=export_request.fields,
        filters=export_request.filters,
        date_from=datetime.combine(export_request.date_from, datetime.min.time()) if export_request.date_from else None,
        date_to=datetime.combine(export_request.date_to, datetime.max.time()) if export_request.date_to else None,
        include_related=export_request.include_related,
        compress=export_request.format == ExportFormat.ZIP
    )
    
    # Generate export ID
    export_id = f"export_{datetime.now().strftime('%Y%m%d%H%M%S')}_{current_user.id}"
    
    # Store initial status
    await redis_client.set(
        f"export:{export_id}",
        ExportProgress(
            export_id=export_id,
            status="pending",
            current=0,
            total=0,
            percentage=0,
            message="Export queued"
        ).json(),
        expire=3600  # 1 hour
    )
    
    # Queue export task
    process_export_task.delay(
        export_id=export_id,
        config=config.dict(),
        user_id=str(current_user.id),
        email_delivery=export_request.email_delivery
    )
    
    return ExportResponse(
        export_id=export_id,
        status="pending",
        created_at=datetime.now()
    )


@router.get("/{export_id}/status", response_model=ExportProgress)
async def get_export_status(
    export_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get export progress status."""
    # Get status from cache
    status_data = await redis_client.get(f"export:{export_id}")
    
    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found"
        )
    
    return ExportProgress.parse_raw(status_data)


@router.get("/{export_id}/download")
async def download_export(
    export_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Download export file."""
    # Get export metadata from cache
    metadata = await redis_client.get(f"export:metadata:{export_id}")
    
    if not metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found or expired"
        )
    
    export_data = ExportResponse.parse_raw(metadata)
    
    # Get file content from cache
    file_content = await redis_client.get(f"export:file:{export_id}")
    
    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file not found or expired"
        )
    
    # Determine MIME type
    mime_types = {
        "csv": "text/csv",
        "json": "application/json",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
        "zip": "application/zip"
    }
    
    format_ext = export_data.filename.split('.')[-1]
    mime_type = mime_types.get(format_ext, "application/octet-stream")
    
    return StreamingResponse(
        io.BytesIO(file_content),
        media_type=mime_type,
        headers={
            "Content-Disposition": f"attachment; filename={export_data.filename}"
        }
    )


@router.post("/direct", response_model=None)
async def direct_export(
    export_request: ExportRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Direct export (synchronous) for small datasets.
    
    Permissions:
    - exports:create
    """
    check_permission(current_user, "exports", "create")
    
    # Create export config
    config = ExportConfig(
        entity_type=export_request.entity_type,
        format=export_request.format,
        fields=export_request.fields,
        filters=export_request.filters,
        date_from=datetime.combine(export_request.date_from, datetime.min.time()) if export_request.date_from else None,
        date_to=datetime.combine(export_request.date_to, datetime.max.time()) if export_request.date_to else None,
        include_related=export_request.include_related
    )
    
    # Perform export
    service = ExportService(db)
    result = await service.export_data(config, current_user)
    
    # Return file directly
    return StreamingResponse(
        io.BytesIO(result.content),
        media_type=result.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename={result.filename}"
        }
    )


@router.get("/templates", response_model=List[ExportTemplate])
async def list_export_templates(
    entity_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List available export templates.
    
    Permissions:
    - exports:read
    """
    check_permission(current_user, "exports", "read")
    
    # TODO: Implement template storage and retrieval
    # For now, return sample templates
    templates = [
        ExportTemplate(
            id="1",
            name="Basic User Export",
            description="Export basic user information",
            entity_type="users",
            format=ExportFormat.CSV,
            fields=["email", "username", "first_name", "last_name", "role", "created_at"],
            is_public=True,
            created_by=str(current_user.id),
            created_at=datetime.now()
        ),
        ExportTemplate(
            id="2",
            name="Model Performance Report",
            description="Export model performance data",
            entity_type="models",
            format=ExportFormat.EXCEL,
            fields=["stage_name", "total_revenue", "total_fans", "commission_rate", "status"],
            filters={"status": "ACTIVE"},
            is_public=True,
            created_by=str(current_user.id),
            created_at=datetime.now()
        ),
        ExportTemplate(
            id="3",
            name="Monthly Transactions",
            description="Export transactions for the current month",
            entity_type="transactions",
            format=ExportFormat.CSV,
            fields=["date", "model_name", "type", "amount", "currency", "status"],
            is_public=True,
            created_by=str(current_user.id),
            created_at=datetime.now()
        )
    ]
    
    if entity_type:
        templates = [t for t in templates if t.entity_type == entity_type]
    
    return templates


@router.post("/templates/{template_id}/export", response_model=ExportResponse)
async def export_from_template(
    template_id: str,
    background_tasks: BackgroundTasks,
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    email_delivery: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create export from template.
    
    Permissions:
    - exports:create
    """
    check_permission(current_user, "exports", "create")
    
    # TODO: Load actual template
    # For now, use hardcoded template
    template_configs = {
        "1": ExportRequest(
            entity_type="users",
            format=ExportFormat.CSV,
            fields=["email", "username", "first_name", "last_name", "role", "created_at"]
        ),
        "2": ExportRequest(
            entity_type="models",
            format=ExportFormat.EXCEL,
            fields=["stage_name", "total_revenue", "total_fans", "commission_rate", "status"],
            filters={"status": "ACTIVE"}
        ),
        "3": ExportRequest(
            entity_type="transactions",
            format=ExportFormat.CSV,
            fields=["date", "model_name", "type", "amount", "currency", "status"]
        )
    }
    
    template_config = template_configs.get(template_id)
    if not template_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Override dates if provided
    if date_from:
        template_config.date_from = date_from.date()
    if date_to:
        template_config.date_to = date_to.date()
    
    template_config.email_delivery = email_delivery
    
    # Create export using template
    return await create_export(
        template_config,
        background_tasks,
        current_user,
        db
    )


@router.get("/history", response_model=List[ExportResponse])
async def get_export_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user)
):
    """Get user's export history."""
    # TODO: Implement export history storage
    # For now, return empty list
    return []


@router.delete("/{export_id}")
async def delete_export(
    export_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Delete export and its files."""
    # Check if export exists
    metadata = await redis_client.get(f"export:metadata:{export_id}")
    
    if not metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found"
        )
    
    # Delete from cache
    await redis_client.delete(f"export:{export_id}")
    await redis_client.delete(f"export:metadata:{export_id}")
    await redis_client.delete(f"export:file:{export_id}")
    
    return {"message": "Export deleted successfully"}
"""Data import API endpoints."""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io
import json

from core.database import get_db
from core.dependencies import get_current_active_user
from core.security_v2.authorization import check_permission
from core.redis import redis_client
from models.user import User
from services.import_service import ImportService
from schemas.import_schema import (
    ImportRequest, ImportResponse, ImportConfig,
    ImportFormat, ImportResult, ImportProgress,
    ImportTemplate, BulkImportJob
)
from tasks.import_tasks import process_import_task
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("", response_model=ImportResponse)
async def create_import(
    file: UploadFile = File(...),
    entity_type: str = Form(...),
    format: ImportFormat = Form(...),
    field_mapping: Optional[str] = Form(None),
    update_existing: bool = Form(False),
    continue_on_error: bool = Form(True),
    validate_only: bool = Form(False),
    send_notifications: bool = Form(True),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new data import.
    
    Permissions:
    - imports:create
    """
    check_permission(current_user, "imports", "create")
    
    # Validate entity type access
    entity_permissions = {
        "users": "users:import",
        "models": "models:import",
        "transactions": "transactions:import",
    }
    
    required_permission = entity_permissions.get(entity_type)
    if required_permission:
        resource, action = required_permission.split(":")
        check_permission(current_user, resource, action)
    
    # Parse field mapping
    field_mapping_dict = None
    if field_mapping:
        try:
            field_mapping_dict = json.loads(field_mapping)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid field mapping JSON"
            )
    
    # Read file content
    file_content = await file.read()
    
    # Generate import ID
    import_id = f"import_{datetime.now().strftime('%Y%m%d%H%M%S')}_{current_user.id}"
    
    # Create import config
    config = ImportConfig(
        entity_type=entity_type,
        format=format,
        field_mapping=field_mapping_dict,
        update_existing=update_existing,
        continue_on_error=continue_on_error,
        validate_only=validate_only,
        task_id=import_id
    )
    
    if validate_only:
        # Perform validation synchronously
        service = ImportService(db)
        result = await service.import_data(file_content, config, current_user)
        
        return ImportResponse(
            import_id=import_id,
            status="validated",
            total_records=result.total_records,
            successful_records=result.successful_records,
            failed_records=result.failed_records,
            created_at=datetime.now()
        )
    else:
        # Store initial status
        await redis_client.set(
            f"import:{import_id}",
            ImportProgress(
                current=0,
                total=0,
                percentage=0,
                status="pending",
                message="Import queued"
            ).json(),
            expire=3600  # 1 hour
        )
        
        # Queue import task
        process_import_task.delay(
            import_id=import_id,
            file_content=file_content.hex(),  # Convert to hex for JSON serialization
            config=config.dict(),
            user_id=str(current_user.id),
            filename=file.filename,
            send_notifications=send_notifications
        )
        
        return ImportResponse(
            import_id=import_id,
            status="pending",
            created_at=datetime.now()
        )


@router.post("/validate", response_model=ImportResult)
async def validate_import(
    file: UploadFile = File(...),
    entity_type: str = Form(...),
    format: ImportFormat = Form(...),
    field_mapping: Optional[str] = Form(None),
    update_existing: bool = Form(False),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Validate import file without importing.
    
    Permissions:
    - imports:create
    """
    check_permission(current_user, "imports", "create")
    
    # Parse field mapping
    field_mapping_dict = None
    if field_mapping:
        try:
            field_mapping_dict = json.loads(field_mapping)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid field mapping JSON"
            )
    
    # Read file content
    file_content = await file.read()
    
    # Create import config
    config = ImportConfig(
        entity_type=entity_type,
        format=format,
        field_mapping=field_mapping_dict,
        update_existing=update_existing,
        validate_only=True
    )
    
    # Perform validation
    service = ImportService(db)
    result = await service.import_data(file_content, config, current_user)
    
    return result


@router.get("/{import_id}/status", response_model=ImportProgress)
async def get_import_status(
    import_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get import progress status."""
    # Get status from cache
    status_data = await redis_client.get(f"import:{import_id}")
    
    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import not found"
        )
    
    return ImportProgress.parse_raw(status_data)


@router.get("/{import_id}/errors")
async def download_import_errors(
    import_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Download import error details."""
    # Get errors from cache
    errors_data = await redis_client.get(f"import:errors:{import_id}")
    
    if not errors_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import errors not found"
        )
    
    # Create CSV with errors
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(["Row Number", "Field", "Value", "Error"])
    
    # Errors
    errors = json.loads(errors_data)
    for error in errors:
        writer.writerow([
            error.get("row_number", ""),
            error.get("field", ""),
            error.get("value", ""),
            error.get("error", "")
        ])
    
    # Return as CSV
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=import_errors_{import_id}.csv"
        }
    )


@router.get("/templates", response_model=List[ImportTemplate])
async def list_import_templates(
    entity_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List available import templates.
    
    Permissions:
    - imports:read
    """
    check_permission(current_user, "imports", "read")
    
    # TODO: Implement template storage and retrieval
    # For now, return sample templates
    templates = [
        ImportTemplate(
            id="1",
            name="Basic User Import",
            description="Import users with basic information",
            entity_type="users",
            format=ImportFormat.CSV,
            field_mappings=[
                {"source_field": "Email", "target_field": "email"},
                {"source_field": "Username", "target_field": "username"},
                {"source_field": "First Name", "target_field": "first_name"},
                {"source_field": "Last Name", "target_field": "last_name"},
                {"source_field": "Role", "target_field": "role"}
            ],
            sample_file_url="/api/v1/imports/templates/1/sample",
            created_by=str(current_user.id),
            created_at=datetime.now()
        ),
        ImportTemplate(
            id="2",
            name="Model Import",
            description="Import models with platform accounts",
            entity_type="models",
            format=ImportFormat.EXCEL,
            field_mappings=[
                {"source_field": "Stage Name", "target_field": "stage_name"},
                {"source_field": "Real Name", "target_field": "real_name"},
                {"source_field": "Email", "target_field": "email"},
                {"source_field": "Phone", "target_field": "phone"},
                {"source_field": "OnlyFans Username", "target_field": "onlyfans_username"},
                {"source_field": "Commission %", "target_field": "commission_rate"}
            ],
            sample_file_url="/api/v1/imports/templates/2/sample",
            created_by=str(current_user.id),
            created_at=datetime.now()
        ),
        ImportTemplate(
            id="3",
            name="Transaction Import",
            description="Import transaction history",
            entity_type="transactions",
            format=ImportFormat.CSV,
            field_mappings=[
                {"source_field": "Date", "target_field": "date"},
                {"source_field": "Model", "target_field": "model_username"},
                {"source_field": "Type", "target_field": "type"},
                {"source_field": "Amount", "target_field": "amount"},
                {"source_field": "Currency", "target_field": "currency"},
                {"source_field": "Description", "target_field": "description"}
            ],
            sample_file_url="/api/v1/imports/templates/3/sample",
            created_by=str(current_user.id),
            created_at=datetime.now()
        )
    ]
    
    if entity_type:
        templates = [t for t in templates if t.entity_type == entity_type]
    
    return templates


@router.get("/templates/{template_id}/sample")
async def download_template_sample(
    template_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Download sample file for import template."""
    # Generate sample files based on template
    samples = {
        "1": {
            "filename": "users_import_sample.csv",
            "content": """Email,Username,First Name,Last Name,Role
john.doe@example.com,johndoe,John,Doe,MEMBER
jane.smith@example.com,janesmith,Jane,Smith,CHATTER
bob.wilson@example.com,bobwilson,Bob,Wilson,MODEL"""
        },
        "2": {
            "filename": "models_import_sample.csv",
            "content": """Stage Name,Real Name,Email,Phone,OnlyFans Username,Commission %
Crystal Rose,Sarah Johnson,sarah@example.com,+1234567890,crystalrose,20
Diamond Blue,Emma Wilson,emma@example.com,+0987654321,diamondblue,25
Ruby Red,Olivia Brown,olivia@example.com,+1122334455,rubyred,20"""
        },
        "3": {
            "filename": "transactions_import_sample.csv",
            "content": """Date,Model,Type,Amount,Currency,Description
2024-01-15,crystalrose,TIP,50.00,USD,Fan tip
2024-01-15,diamondblue,SUBSCRIPTION,29.99,USD,Monthly subscription
2024-01-16,rubyred,MESSAGE,10.00,USD,PPV message"""
        }
    }
    
    sample = samples.get(template_id)
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    return StreamingResponse(
        io.BytesIO(sample["content"].encode('utf-8')),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={sample['filename']}"
        }
    )


@router.get("/history", response_model=List[BulkImportJob])
async def get_import_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    entity_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's import history.
    
    Permissions:
    - imports:read
    """
    check_permission(current_user, "imports", "read")
    
    # TODO: Implement import history storage
    # For now, return sample data
    jobs = [
        BulkImportJob(
            id="import_20240115_120000",
            entity_type="users",
            filename="new_users.csv",
            status="completed",
            total_records=100,
            processed_records=100,
            successful_records=95,
            failed_records=5,
            started_at=datetime.now() - timedelta(hours=2),
            completed_at=datetime.now() - timedelta(hours=1, minutes=30),
            created_by=str(current_user.id),
            error_details_url="/api/v1/imports/import_20240115_120000/errors"
        )
    ]
    
    # Apply filters
    if entity_type:
        jobs = [j for j in jobs if j.entity_type == entity_type]
    if status:
        jobs = [j for j in jobs if j.status == status]
    
    # Paginate
    return jobs[skip:skip + limit]


@router.delete("/{import_id}")
async def cancel_import(
    import_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Cancel ongoing import."""
    # Check if import exists
    status_data = await redis_client.get(f"import:{import_id}")
    
    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import not found"
        )
    
    # Update status to cancelled
    progress = ImportProgress.parse_raw(status_data)
    progress.status = "cancelled"
    progress.message = "Import cancelled by user"
    
    await redis_client.set(
        f"import:{import_id}",
        progress.json(),
        expire=3600
    )
    
    # TODO: Actually cancel the background task
    
    return {"message": "Import cancelled successfully"}
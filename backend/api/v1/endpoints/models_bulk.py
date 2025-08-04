"""Bulk operations for model management."""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from core.database import get_db
from models.user import User, UserRole
from models.model import Model, ModelStatus
from api.v1.endpoints.auth_simple import get_current_user
from core.logger import get_logger
from services.email_notifications import EmailNotificationService

logger = get_logger(__name__)

router = APIRouter()


class BulkModelUpdate(BaseModel):
    """Bulk update request model."""
    model_ids: List[int] = Field(..., min_items=1, max_items=100)
    status: Optional[ModelStatus] = None
    chat_enabled: Optional[bool] = None
    commission_rate: Optional[float] = Field(None, ge=0, le=100)
    tags: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    action: Optional[str] = Field(None, regex="^(add|remove|replace)$")


class BulkModelDelete(BaseModel):
    """Bulk delete request model."""
    model_ids: List[int] = Field(..., min_items=1, max_items=100)
    permanent: bool = False


class ModelApproval(BaseModel):
    """Model approval request."""
    model_id: int
    approved: bool
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None


class BulkOperationResponse(BaseModel):
    """Response for bulk operations."""
    total: int
    successful: int
    failed: int
    errors: List[Dict[str, Any]] = []


@router.post("/bulk/update", response_model=BulkOperationResponse)
async def bulk_update_models(
    update_data: BulkModelUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Bulk update multiple models."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions for bulk operations")
    
    response = BulkOperationResponse(
        total=len(update_data.model_ids),
        successful=0,
        failed=0,
        errors=[]
    )
    
    # Get models based on user role
    query = select(Model).where(Model.id.in_(update_data.model_ids))
    if current_user.role != UserRole.SUPER_ADMIN:
        query = query.where(Model.agency_id == current_user.agency_id)
    
    models = await db.scalars(query)
    models_dict = {m.id: m for m in models}
    
    # Process each model
    for model_id in update_data.model_ids:
        try:
            model = models_dict.get(model_id)
            if not model:
                response.failed += 1
                response.errors.append({
                    "model_id": model_id,
                    "error": "Model not found or access denied"
                })
                continue
            
            # Update status
            if update_data.status is not None:
                model.status = update_data.status
            
            # Update chat_enabled
            if update_data.chat_enabled is not None:
                model.chat_enabled = update_data.chat_enabled
            
            # Update commission_rate
            if update_data.commission_rate is not None:
                model.commission_rate = update_data.commission_rate
            
            # Handle tags and categories based on action
            if update_data.tags is not None and update_data.action:
                if update_data.action == "add":
                    model.tags = list(set(model.tags or []) | set(update_data.tags))
                elif update_data.action == "remove":
                    model.tags = [t for t in (model.tags or []) if t not in update_data.tags]
                elif update_data.action == "replace":
                    model.tags = update_data.tags
            
            if update_data.categories is not None and update_data.action:
                if update_data.action == "add":
                    model.categories = list(set(model.categories or []) | set(update_data.categories))
                elif update_data.action == "remove":
                    model.categories = [c for c in (model.categories or []) if c not in update_data.categories]
                elif update_data.action == "replace":
                    model.categories = update_data.categories
            
            model.updated_at = datetime.utcnow()
            response.successful += 1
            
        except Exception as e:
            response.failed += 1
            response.errors.append({
                "model_id": model_id,
                "error": str(e)
            })
            logger.error(f"Error updating model {model_id}: {e}")
    
    await db.commit()
    return response


@router.post("/bulk/delete", response_model=BulkOperationResponse)
async def bulk_delete_models(
    delete_data: BulkModelDelete,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Bulk delete multiple models."""
    # Check permissions - only super admin and agency owner can bulk delete
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions for bulk delete")
    
    response = BulkOperationResponse(
        total=len(delete_data.model_ids),
        successful=0,
        failed=0,
        errors=[]
    )
    
    # Get models
    query = select(Model).where(Model.id.in_(delete_data.model_ids))
    if current_user.role != UserRole.SUPER_ADMIN:
        query = query.where(Model.agency_id == current_user.agency_id)
    
    models = await db.scalars(query)
    models_list = list(models)
    
    for model in models_list:
        try:
            if delete_data.permanent and current_user.role == UserRole.SUPER_ADMIN:
                # Hard delete - only super admin
                await db.delete(model)
            else:
                # Soft delete
                model.status = ModelStatus.DELETED
                model.updated_at = datetime.utcnow()
                
                # Deactivate associated user
                user_stmt = select(User).where(User.id == model.user_id)
                model_user = await db.scalar(user_stmt)
                if model_user:
                    model_user.is_active = False
            
            response.successful += 1
            
        except Exception as e:
            response.failed += 1
            response.errors.append({
                "model_id": model.id,
                "error": str(e)
            })
            logger.error(f"Error deleting model {model.id}: {e}")
    
    # Handle models not found
    found_ids = [m.id for m in models_list]
    for model_id in delete_data.model_ids:
        if model_id not in found_ids:
            response.failed += 1
            response.errors.append({
                "model_id": model_id,
                "error": "Model not found or access denied"
            })
    
    await db.commit()
    return response


@router.post("/approve", response_model=Dict[str, Any])
async def approve_model(
    approval_data: ModelApproval,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Approve or reject a model."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions to approve models")
    
    # Get model
    query = select(Model).where(Model.id == approval_data.model_id)
    if current_user.role != UserRole.SUPER_ADMIN:
        query = query.where(Model.agency_id == current_user.agency_id)
    
    model = await db.scalar(query)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Check current status
    if model.status not in [ModelStatus.PENDING, ModelStatus.UNDER_REVIEW]:
        raise HTTPException(
            status_code=400, 
            detail=f"Model cannot be approved/rejected in {model.status} status"
        )
    
    # Update status
    if approval_data.approved:
        model.status = ModelStatus.ACTIVE
        model.verification_status = "verified"
        model.verified_at = datetime.utcnow()
        
        # Activate user account
        user_stmt = select(User).where(User.id == model.user_id)
        model_user = await db.scalar(user_stmt)
        if model_user:
            model_user.is_active = True
            
        message = "Model approved successfully"
    else:
        model.status = ModelStatus.REJECTED
        model.rejection_reason = approval_data.rejection_reason
        message = "Model rejected"
    
    # Add approval note
    if approval_data.notes:
        model.admin_notes = (model.admin_notes or "") + f"\n[{datetime.utcnow().isoformat()}] {approval_data.notes}"
    
    model.updated_at = datetime.utcnow()
    model.reviewed_by = current_user.id
    model.reviewed_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(model)
    
    # Send email notification about approval/rejection
    email_service = EmailNotificationService(db)
    await email_service.send_model_approval_email(
        model=model,
        approved=approval_data.approved,
        reason=approval_data.rejection_reason,
        admin_notes=approval_data.notes
    )
    
    return {
        "message": message,
        "model_id": model.id,
        "status": model.status.value,
        "verified": model.verification_status == "verified"
    }


@router.get("/pending-approval", response_model=List[Dict[str, Any]])
async def get_pending_models(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
    offset: int = 0
):
    """Get models pending approval."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Build query
    query = select(Model).where(
        Model.status.in_([ModelStatus.PENDING, ModelStatus.UNDER_REVIEW])
    ).order_by(Model.created_at.desc())
    
    if current_user.role != UserRole.SUPER_ADMIN:
        query = query.where(Model.agency_id == current_user.agency_id)
    
    query = query.limit(limit).offset(offset)
    
    models = await db.scalars(query)
    
    return [
        {
            "id": model.id,
            "stage_name": model.stage_name,
            "real_name": model.real_name,
            "platform": model.platform.value,
            "platform_username": model.platform_username,
            "status": model.status.value,
            "created_at": model.created_at.isoformat(),
            "profile_photo_url": model.profile_photo_url,
            "agency_id": model.agency_id,
            "documents_uploaded": bool(model.id_document_url),
            "profile_complete": all([
                model.stage_name,
                model.platform,
                model.platform_username,
                model.bio,
                model.profile_photo_url
            ])
        }
        for model in models
    ]
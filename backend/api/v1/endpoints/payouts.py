"""Payout management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from pydantic import BaseModel, Field
import uuid

from core.database import get_db
from models.user import User, UserRole
from models.model import Model
from models.financial import Payout, PayoutStatus, Earning, Transaction, PaymentMethod
from models.payment_method import PaymentMethodModel
from api.v1.endpoints.auth_simple import get_current_user
from core.logger import get_logger
from services.email_notifications import EmailNotificationService

logger = get_logger(__name__)

router = APIRouter()


# Request/Response Models
class PayoutCreate(BaseModel):
    """Create a new payout."""
    model_id: int
    period_start: str
    period_end: str
    payment_method_id: int
    adjustments: Decimal = Field(default=Decimal("0.00"))
    notes: Optional[str] = None
    scheduled_date: Optional[str] = None


class PayoutUpdate(BaseModel):
    """Update payout details."""
    status: Optional[PayoutStatus] = None
    payment_method_id: Optional[int] = None
    adjustments: Optional[Decimal] = None
    notes: Optional[str] = None
    scheduled_date: Optional[str] = None


class PayoutApproval(BaseModel):
    """Approve or reject a payout."""
    approved: bool
    notes: Optional[str] = None


class PayoutBulkAction(BaseModel):
    """Bulk action on payouts."""
    payout_ids: List[int]
    action: str = Field(..., pattern="^(approve|process|cancel)$")
    notes: Optional[str] = None


class PayoutResponse(BaseModel):
    """Payout response model."""
    id: int
    payout_number: str
    model_id: int
    model_name: str
    status: PayoutStatus
    period_start: str
    period_end: str
    gross_earnings: Decimal
    commission_amount: Decimal
    adjustments: Decimal
    net_amount: Decimal
    currency: str
    payment_method: Dict[str, Any]
    scheduled_date: str
    processed_date: Optional[str]
    completed_date: Optional[str]
    notes: Optional[str]
    earnings_count: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@router.get("/", response_model=List[PayoutResponse])
async def get_payouts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status: Optional[PayoutStatus] = None,
    model_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get payouts with filters."""
    # Base query
    query = select(Payout).join(Model)
    
    # Apply filters based on user role
    if current_user.role == UserRole.MODEL:
        # Models can only see their own payouts
        model = await db.scalar(select(Model).where(Model.user_id == current_user.id))
        if not model:
            raise HTTPException(status_code=404, detail="Model profile not found")
        query = query.where(Payout.model_id == model.id)
    elif current_user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        # Agency users see their agency's payouts
        query = query.where(Payout.agency_id == current_user.agency_id)
    # Super admins can see all payouts
    
    # Apply filters
    if status:
        query = query.where(Payout.status == status)
    if model_id:
        query = query.where(Payout.model_id == model_id)
    if start_date:
        query = query.where(Payout.scheduled_date >= start_date)
    if end_date:
        query = query.where(Payout.scheduled_date <= end_date)
    
    # Order and paginate
    query = query.order_by(Payout.created_at.desc()).limit(limit).offset(offset)
    
    payouts = await db.scalars(query)
    
    # Format response
    result = []
    for payout in payouts:
        # Get model info
        model = await db.get(Model, payout.model_id)
        
        # Get payment method
        payment_method = await db.scalar(
            select(PaymentMethodModel).where(
                PaymentMethodModel.id == payout.payment_details.get('payment_method_id')
            )
        )
        
        result.append(PayoutResponse(
            id=payout.id,
            payout_number=payout.payout_number,
            model_id=payout.model_id,
            model_name=model.stage_name if model else "Unknown",
            status=payout.status,
            period_start=payout.period_start,
            period_end=payout.period_end,
            gross_earnings=payout.gross_earnings,
            commission_amount=payout.commission_amount,
            adjustments=payout.adjustments,
            net_amount=payout.net_amount,
            currency=payout.currency,
            payment_method=payment_method.mask_sensitive_data() if payment_method else {},
            scheduled_date=payout.scheduled_date,
            processed_date=payout.processed_date,
            completed_date=payout.completed_date,
            notes=payout.notes,
            earnings_count=len(payout.earnings),
            created_at=payout.created_at,
            updated_at=payout.updated_at
        ))
    
    return result


@router.post("/", response_model=PayoutResponse)
async def create_payout(
    payout_data: PayoutCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new payout for a model."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get model
    model = await db.get(Model, payout_data.model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Verify agency access
    if current_user.role != UserRole.SUPER_ADMIN and model.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Cannot create payout for model from different agency")
    
    # Get payment method
    payment_method = await db.get(PaymentMethodModel, payout_data.payment_method_id)
    if not payment_method or payment_method.model_id != model.id:
        raise HTTPException(status_code=404, detail="Payment method not found")
    
    # Calculate payout from unpaid earnings
    earnings_query = select(Earning).where(
        and_(
            Earning.model_id == model.id,
            Earning.is_paid == False,
            Earning.created_at >= payout_data.period_start,
            Earning.created_at <= payout_data.period_end
        )
    )
    earnings = await db.scalars(earnings_query)
    earnings_list = list(earnings)
    
    if not earnings_list:
        raise HTTPException(status_code=400, detail="No unpaid earnings found for the specified period")
    
    # Calculate totals
    gross_earnings = sum(e.gross_amount for e in earnings_list)
    commission_amount = sum(e.commission_amount for e in earnings_list)
    net_amount = gross_earnings - commission_amount + payout_data.adjustments
    
    # Generate payout number
    payout_number = f"PO-{datetime.utcnow().strftime('%Y%m')}-{uuid.uuid4().hex[:8].upper()}"
    
    # Create payout
    payout = Payout(
        agency_id=model.agency_id,
        model_id=model.id,
        payout_number=payout_number,
        status=PayoutStatus.PENDING,
        period_start=payout_data.period_start,
        period_end=payout_data.period_end,
        gross_earnings=gross_earnings,
        commission_amount=commission_amount,
        adjustments=payout_data.adjustments,
        net_amount=net_amount,
        currency="USD",
        payment_method=payment_method.method_type,
        payment_details={
            'payment_method_id': payment_method.id,
            'method_type': payment_method.method_type.value,
            'display_name': payment_method.display_name
        },
        scheduled_date=payout_data.scheduled_date or datetime.utcnow().isoformat(),
        notes=payout_data.notes
    )
    db.add(payout)
    await db.flush()
    
    # Mark earnings as paid and link to payout
    for earning in earnings_list:
        earning.is_paid = True
        earning.payout_id = payout.id
        earning.paid_date = datetime.utcnow().isoformat()
    
    await db.commit()
    await db.refresh(payout)
    
    # Send email notification
    email_service = EmailNotificationService(db)
    await email_service.send_payout_created_email(payout)
    
    # Return response
    return PayoutResponse(
        id=payout.id,
        payout_number=payout.payout_number,
        model_id=payout.model_id,
        model_name=model.stage_name,
        status=payout.status,
        period_start=payout.period_start,
        period_end=payout.period_end,
        gross_earnings=payout.gross_earnings,
        commission_amount=payout.commission_amount,
        adjustments=payout.adjustments,
        net_amount=payout.net_amount,
        currency=payout.currency,
        payment_method=payment_method.mask_sensitive_data(),
        scheduled_date=payout.scheduled_date,
        processed_date=payout.processed_date,
        completed_date=payout.completed_date,
        notes=payout.notes,
        earnings_count=len(earnings_list),
        created_at=payout.created_at,
        updated_at=payout.updated_at
    )


@router.get("/{payout_id}", response_model=PayoutResponse)
async def get_payout(
    payout_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific payout."""
    payout = await db.get(Payout, payout_id)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    
    # Check access
    if current_user.role == UserRole.MODEL:
        model = await db.scalar(select(Model).where(Model.user_id == current_user.id))
        if not model or payout.model_id != model.id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        if payout.agency_id != current_user.agency_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Get model and payment method
    model = await db.get(Model, payout.model_id)
    payment_method = await db.scalar(
        select(PaymentMethodModel).where(
            PaymentMethodModel.id == payout.payment_details.get('payment_method_id')
        )
    )
    
    return PayoutResponse(
        id=payout.id,
        payout_number=payout.payout_number,
        model_id=payout.model_id,
        model_name=model.stage_name if model else "Unknown",
        status=payout.status,
        period_start=payout.period_start,
        period_end=payout.period_end,
        gross_earnings=payout.gross_earnings,
        commission_amount=payout.commission_amount,
        adjustments=payout.adjustments,
        net_amount=payout.net_amount,
        currency=payout.currency,
        payment_method=payment_method.mask_sensitive_data() if payment_method else {},
        scheduled_date=payout.scheduled_date,
        processed_date=payout.processed_date,
        completed_date=payout.completed_date,
        notes=payout.notes,
        earnings_count=len(payout.earnings),
        created_at=payout.created_at,
        updated_at=payout.updated_at
    )


@router.patch("/{payout_id}", response_model=PayoutResponse)
async def update_payout(
    payout_id: int,
    update_data: PayoutUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a payout."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    payout = await db.get(Payout, payout_id)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    
    # Verify agency access
    if current_user.role != UserRole.SUPER_ADMIN and payout.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if payout can be updated
    if payout.status in [PayoutStatus.COMPLETED, PayoutStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail=f"Cannot update {payout.status} payout")
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    
    # Handle payment method update
    if 'payment_method_id' in update_dict:
        payment_method = await db.get(PaymentMethodModel, update_dict['payment_method_id'])
        if not payment_method or payment_method.model_id != payout.model_id:
            raise HTTPException(status_code=404, detail="Payment method not found")
        
        payout.payment_method = payment_method.method_type
        payout.payment_details = {
            'payment_method_id': payment_method.id,
            'method_type': payment_method.method_type.value,
            'display_name': payment_method.display_name
        }
        del update_dict['payment_method_id']
    
    # Update status timestamps
    if 'status' in update_dict:
        if update_dict['status'] == PayoutStatus.PROCESSING:
            payout.processed_date = datetime.utcnow().isoformat()
        elif update_dict['status'] == PayoutStatus.COMPLETED:
            payout.completed_date = datetime.utcnow().isoformat()
    
    # Apply other updates
    for field, value in update_dict.items():
        if hasattr(payout, field):
            setattr(payout, field, value)
    
    payout.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(payout)
    
    # Get updated info
    model = await db.get(Model, payout.model_id)
    payment_method = await db.scalar(
        select(PaymentMethodModel).where(
            PaymentMethodModel.id == payout.payment_details.get('payment_method_id')
        )
    )
    
    return PayoutResponse(
        id=payout.id,
        payout_number=payout.payout_number,
        model_id=payout.model_id,
        model_name=model.stage_name if model else "Unknown",
        status=payout.status,
        period_start=payout.period_start,
        period_end=payout.period_end,
        gross_earnings=payout.gross_earnings,
        commission_amount=payout.commission_amount,
        adjustments=payout.adjustments,
        net_amount=payout.net_amount,
        currency=payout.currency,
        payment_method=payment_method.mask_sensitive_data() if payment_method else {},
        scheduled_date=payout.scheduled_date,
        processed_date=payout.processed_date,
        completed_date=payout.completed_date,
        notes=payout.notes,
        earnings_count=len(payout.earnings),
        created_at=payout.created_at,
        updated_at=payout.updated_at
    )


@router.post("/{payout_id}/approve", response_model=Dict[str, Any])
async def approve_payout(
    payout_id: int,
    approval_data: PayoutApproval,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Approve or reject a payout."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Only owners can approve payouts")
    
    payout = await db.get(Payout, payout_id)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    
    # Verify agency access
    if current_user.role != UserRole.SUPER_ADMIN and payout.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check current status
    if payout.status != PayoutStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending payouts can be approved")
    
    if approval_data.approved:
        payout.status = PayoutStatus.PROCESSING
        payout.processed_date = datetime.utcnow().isoformat()
        message = "Payout approved and queued for processing"
    else:
        payout.status = PayoutStatus.CANCELLED
        message = "Payout rejected"
    
    if approval_data.notes:
        payout.notes = (payout.notes or "") + f"\n[{datetime.utcnow().isoformat()}] {approval_data.notes}"
    
    payout.updated_at = datetime.utcnow()
    
    await db.commit()
    
    # Send email notification if approved
    if approval_data.approved:
        email_service = EmailNotificationService(db)
        await email_service.send_payout_approved_email(payout)
    
    return {
        "message": message,
        "payout_id": payout.id,
        "status": payout.status.value
    }


@router.post("/bulk-action", response_model=Dict[str, Any])
async def bulk_payout_action(
    action_data: PayoutBulkAction,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Perform bulk action on multiple payouts."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions for bulk actions")
    
    # Get payouts
    query = select(Payout).where(Payout.id.in_(action_data.payout_ids))
    if current_user.role != UserRole.SUPER_ADMIN:
        query = query.where(Payout.agency_id == current_user.agency_id)
    
    payouts = await db.scalars(query)
    payouts_list = list(payouts)
    
    if not payouts_list:
        raise HTTPException(status_code=404, detail="No payouts found")
    
    success_count = 0
    error_count = 0
    errors = []
    
    for payout in payouts_list:
        try:
            if action_data.action == "approve":
                if payout.status == PayoutStatus.PENDING:
                    payout.status = PayoutStatus.PROCESSING
                    payout.processed_date = datetime.utcnow().isoformat()
                    success_count += 1
                else:
                    errors.append(f"Payout {payout.payout_number} is not pending")
                    error_count += 1
                    
            elif action_data.action == "process":
                if payout.status == PayoutStatus.PROCESSING:
                    payout.status = PayoutStatus.COMPLETED
                    payout.completed_date = datetime.utcnow().isoformat()
                    success_count += 1
                else:
                    errors.append(f"Payout {payout.payout_number} is not in processing status")
                    error_count += 1
                    
            elif action_data.action == "cancel":
                if payout.status in [PayoutStatus.PENDING, PayoutStatus.PROCESSING]:
                    payout.status = PayoutStatus.CANCELLED
                    success_count += 1
                else:
                    errors.append(f"Payout {payout.payout_number} cannot be cancelled")
                    error_count += 1
            
            if action_data.notes:
                payout.notes = (payout.notes or "") + f"\n[{datetime.utcnow().isoformat()}] Bulk action: {action_data.notes}"
            
            payout.updated_at = datetime.utcnow()
            
        except Exception as e:
            errors.append(f"Error processing payout {payout.payout_number}: {str(e)}")
            error_count += 1
    
    await db.commit()
    
    return {
        "message": f"Bulk action completed",
        "action": action_data.action,
        "total": len(payouts_list),
        "success": success_count,
        "errors": error_count,
        "error_details": errors if errors else None
    }


@router.get("/{payout_id}/earnings", response_model=List[Dict[str, Any]])
async def get_payout_earnings(
    payout_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get earnings included in a payout."""
    payout = await db.get(Payout, payout_id)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    
    # Check access
    if current_user.role == UserRole.MODEL:
        model = await db.scalar(select(Model).where(Model.user_id == current_user.id))
        if not model or payout.model_id != model.id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        if payout.agency_id != current_user.agency_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Get earnings
    earnings = await db.scalars(
        select(Earning).where(Earning.payout_id == payout_id).order_by(Earning.created_at.desc())
    )
    
    return [
        {
            "id": earning.id,
            "transaction_id": earning.transaction_id,
            "type": earning.type,
            "gross_amount": earning.gross_amount,
            "commission_amount": earning.commission_amount,
            "net_amount": earning.net_amount,
            "created_at": earning.created_at,
            "period_year": earning.period_year,
            "period_month": earning.period_month,
        }
        for earning in earnings
    ]
"""Financial and transaction management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from pydantic import BaseModel, Field

from core.database import get_db
from core.auth.decorators import require_roles, require_admin, require_model_assignment
from models.user import User, UserRole
from models.agency import Agency
from models.model import Model
from models.financial import (
    Transaction, TransactionType, TransactionStatus,
    Payout, PayoutStatus, PaymentMethod,
    Invoice
)
from models.chat import Conversation as Chat
from api.v1.endpoints.auth_simple import get_current_user
from core.errors import NotFoundError, AuthorizationError, ValidationError as AppValidationError
from core.logger import get_logger
from services.commission_service import CommissionService

logger = get_logger(__name__)


router = APIRouter()


# Request/Response Models
class TransactionCreate(BaseModel):
    model_id: int
    user_id: int
    amount: Decimal = Field(..., gt=0)
    type: TransactionType
    chat_id: Optional[int] = None
    content_id: Optional[int] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}


class TransactionResponse(BaseModel):
    id: int
    model_id: int
    model_name: str
    user_id: int
    user_name: str
    chat_id: Optional[int]
    content_id: Optional[int]
    type: TransactionType
    status: TransactionStatus
    gross_amount: Decimal
    platform_fee: Decimal
    agency_fee: Decimal
    model_earnings: Decimal
    description: Optional[str]
    payment_method: Optional[str]
    external_id: Optional[str]
    metadata: Dict[str, Any]
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class PayoutCreate(BaseModel):
    model_id: int
    amount: Decimal = Field(..., gt=0)  # User input amount
    payment_method: PaymentMethod
    payment_details: Dict[str, Any]
    notes: Optional[str] = None


class PayoutResponse(BaseModel):
    id: int
    model_id: int
    model_name: str
    agency_id: int
    net_amount: Decimal
    status: PayoutStatus
    payment_method: PaymentMethod
    payment_details: Dict[str, Any]
    external_id: Optional[str]
    notes: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    id: int
    agency_id: int
    invoice_number: str
    period_start: datetime
    period_end: datetime
    total_amount: Decimal
    status: str
    due_date: datetime
    paid_at: Optional[datetime]
    items: List[Dict[str, Any]]
    created_at: datetime
    
    class Config:
        from_attributes = True


class FinancialSummary(BaseModel):
    total_revenue: Decimal
    pending_payouts: Decimal
    completed_payouts: Decimal
    available_balance: Decimal
    current_month_revenue: Decimal
    last_month_revenue: Decimal
    revenue_by_type: Dict[str, Decimal]
    recent_transactions: List[TransactionResponse]


# Helper functions
async def verify_model_access(model_id: int, user: User, db: AsyncSession) -> Model:
    """Verify user has access to the model."""
    stmt = select(Model).where(Model.id == model_id)
    
    if user.role != UserRole.SUPER_ADMIN:
        if user.role == UserRole.MODEL:
            stmt = stmt.where(Model.user_id == user.id)
        elif user.agency_id:
            stmt = stmt.where(Model.agency_id == user.agency_id)
        else:
            raise AuthorizationError("Access denied to model information")
    
    model = await db.scalar(stmt)
    if not model:
        raise NotFoundError("Model", model_id)
    
    return model


# Endpoints
@router.get("/transactions", response_model=List[TransactionResponse])
@require_roles([UserRole.SUPER_ADMIN.value, UserRole.AGENCY_OWNER.value, UserRole.AGENCY_ADMIN.value, UserRole.MODEL.value])
async def list_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    model_id: Optional[int] = None,
    type: Optional[TransactionType] = None,
    status: Optional[TransactionStatus] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List transactions with filtering and pagination."""
    # Build base query
    query = select(Transaction)
    
    # Apply access filters
    if current_user.role == UserRole.MODEL:
        model_stmt = select(Model.id).where(Model.user_id == current_user.id)
        model_ids = await db.scalar(model_stmt)
        if model_ids:
            query = query.where(Transaction.model_id == model_ids)
        else:
            return []
    elif current_user.role != UserRole.SUPER_ADMIN and current_user.agency_id:
        query = query.where(Transaction.agency_id == current_user.agency_id)
    
    # Apply filters
    if model_id:
        query = query.where(Transaction.model_id == model_id)
    
    if type:
        query = query.where(Transaction.type == type)
    
    if status:
        query = query.where(Transaction.status == status)
    
    if start_date:
        query = query.where(Transaction.created_at >= start_date)
    
    if end_date:
        query = query.where(Transaction.created_at <= end_date)
    
    # Apply pagination
    offset = (page - 1) * limit
    query = query.order_by(Transaction.created_at.desc()).offset(offset).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    transactions = result.scalars().all()
    
    # Build response
    response = []
    for trans in transactions:
        # Get model and user names
        model_stmt = select(Model).where(Model.id == trans.model_id)
        model = await db.scalar(model_stmt)
        
        user_stmt = select(User).where(User.id == trans.user_id)
        user = await db.scalar(user_stmt)
        
        response.append(TransactionResponse(
            id=trans.id,
            model_id=trans.model_id,
            model_name=model.stage_name if model else "Unknown",
            user_id=trans.user_id,
            user_name=f"{user.first_name} {user.last_name}" if user else "Unknown",
            chat_id=trans.chat_id,
            content_id=trans.content_id,
            type=trans.type,
            status=trans.status,
            gross_amount=trans.gross_amount,
            platform_fee=trans.platform_fee,
            agency_fee=trans.agency_fee,
            model_earnings=trans.model_earnings,
            description=trans.description,
            payment_method=trans.payment_method,
            external_id=trans.external_id,
            metadata=trans.metadata or {},
            created_at=trans.created_at,
            completed_at=trans.completed_at
        ))
    
    return response


@router.post("/transactions", response_model=TransactionResponse)
@require_admin()
async def create_transaction(
    transaction_data: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new transaction."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Verify model exists and get agency
    model = await verify_model_access(transaction_data.model_id, current_user, db)
    
    # Calculate fees using commission service
    commission_service = CommissionService(db)
    gross_amount = transaction_data.amount
    
    fees = await commission_service.calculate_transaction_fees(
        model_id=transaction_data.model_id,
        gross_amount=gross_amount,
        transaction_date=datetime.utcnow()
    )
    
    platform_fee = fees["platform_fee"]
    agency_fee = fees["agency_fee"]
    model_earnings = fees["model_earnings"]
    
    # Create transaction
    transaction = Transaction(
        model_id=transaction_data.model_id,
        agency_id=model.agency_id,
        user_id=transaction_data.user_id,
        chat_id=transaction_data.chat_id,
        content_id=transaction_data.content_id,
        type=transaction_data.type,
        status=TransactionStatus.PENDING,
        gross_amount=gross_amount,
        platform_fee=platform_fee,
        agency_fee=agency_fee,
        model_earnings=model_earnings,
        description=transaction_data.description,
        metadata=transaction_data.metadata or {}
    )
    
    db.add(transaction)
    
    # Update model balance
    model.pending_payout += model_earnings
    model.total_earnings += model_earnings
    
    # Mark as completed (in production this would happen after payment processing)
    transaction.status = TransactionStatus.COMPLETED
    transaction.completed_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(transaction)
    
    # Get names for response
    user_stmt = select(User).where(User.id == transaction.user_id)
    user = await db.scalar(user_stmt)
    
    return TransactionResponse(
        id=transaction.id,
        model_id=transaction.model_id,
        model_name=model.stage_name,
        user_id=transaction.user_id,
        user_name=f"{user.first_name} {user.last_name}" if user else "Unknown",
        chat_id=transaction.chat_id,
        content_id=transaction.content_id,
        type=transaction.type,
        status=transaction.status,
        gross_amount=transaction.gross_amount,
        platform_fee=transaction.platform_fee,
        agency_fee=transaction.agency_fee,
        model_earnings=transaction.model_earnings,
        description=transaction.description,
        payment_method=transaction.payment_method,
        external_id=transaction.external_id,
        metadata=transaction.metadata,
        created_at=transaction.created_at,
        completed_at=transaction.completed_at
    )


@router.get("/payouts", response_model=List[PayoutResponse])
@require_roles([UserRole.SUPER_ADMIN.value, UserRole.AGENCY_OWNER.value, UserRole.AGENCY_ADMIN.value, UserRole.MODEL.value])
async def list_payouts(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    model_id: Optional[int] = None,
    status: Optional[PayoutStatus] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List payouts with filtering and pagination."""
    # Build base query
    query = select(Payout)
    
    # Apply access filters
    if current_user.role == UserRole.MODEL:
        model_stmt = select(Model.id).where(Model.user_id == current_user.id)
        model_ids = await db.scalar(model_stmt)
        if model_ids:
            query = query.where(Payout.model_id == model_ids)
        else:
            return []
    elif current_user.role != UserRole.SUPER_ADMIN and current_user.agency_id:
        query = query.where(Payout.agency_id == current_user.agency_id)
    
    # Apply filters
    if model_id:
        query = query.where(Payout.model_id == model_id)
    
    if status:
        query = query.where(Payout.status == status)
    
    # Apply pagination
    offset = (page - 1) * limit
    query = query.order_by(Payout.created_at.desc()).offset(offset).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    payouts = result.scalars().all()
    
    # Build response
    response = []
    for payout in payouts:
        # Get model name
        model_stmt = select(Model).where(Model.id == payout.model_id)
        model = await db.scalar(model_stmt)
        
        response.append(PayoutResponse(
            id=payout.id,
            model_id=payout.model_id,
            model_name=model.stage_name if model else "Unknown",
            agency_id=payout.agency_id,
            net_amount=payout.net_amount,
            status=payout.status,
            payment_method=payout.payment_method,
            payment_details=payout.payment_details or {},
            external_id=payout.external_id,
            notes=payout.notes,
            created_at=payout.created_at,
            processed_at=payout.processed_date
        ))
    
    return response


@router.post("/payouts", response_model=PayoutResponse)
@require_admin()
async def create_payout(
    payout_data: PayoutCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new payout request."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Verify model and check balance
    model = await verify_model_access(payout_data.model_id, current_user, db)
    
    if model.pending_payout < payout_data.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    # Create payout (using the Payout model fields)
    from datetime import datetime
    payout = Payout(
        model_id=payout_data.model_id,
        agency_id=model.agency_id,
        payout_number=f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{model.id}",
        status=PayoutStatus.PENDING,
        net_amount=payout_data.amount,  # Using net_amount field
        gross_earnings=payout_data.amount,  # Simplified for now
        commission_amount=Decimal("0"),
        adjustments=Decimal("0"),
        currency="USD",
        payment_method=payout_data.payment_method,
        payment_details=payout_data.payment_details,
        scheduled_date=datetime.utcnow().isoformat(),
        notes=payout_data.notes
    )
    
    db.add(payout)
    
    # Update model balance
    model.pending_payout -= payout_data.amount
    
    await db.commit()
    await db.refresh(payout)
    
    return PayoutResponse(
        id=payout.id,
        model_id=payout.model_id,
        model_name=model.stage_name,
        agency_id=payout.agency_id,
        net_amount=payout.net_amount,
        status=payout.status,
        payment_method=payout.payment_method,
        payment_details=payout.payment_details,
        external_id=payout.transaction_reference,
        notes=payout.notes,
        created_at=payout.created_at,
        processed_at=payout.processed_date
    )


@router.patch("/payouts/{payout_id}/process")
@require_admin()
async def process_payout(
    payout_id: int,
    external_id: str,
    status: PayoutStatus,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Process a payout (mark as completed/failed)."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get payout
    stmt = select(Payout).where(Payout.id == payout_id)
    if current_user.agency_id:
        stmt = stmt.where(Payout.agency_id == current_user.agency_id)
    
    payout = await db.scalar(stmt)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    
    # Update payout
    payout.status = status
    payout.transaction_reference = external_id
    payout.processed_date = datetime.utcnow().isoformat()
    
    # If failed, refund the balance
    if status == PayoutStatus.FAILED:
        model_stmt = select(Model).where(Model.id == payout.model_id)
        model = await db.scalar(model_stmt)
        if model:
            model.pending_payout += payout.net_amount
    
    await db.commit()
    
    return {"message": f"Payout {status.value}"}


@router.get("/summary", response_model=FinancialSummary)
@require_roles([UserRole.SUPER_ADMIN.value, UserRole.AGENCY_OWNER.value, UserRole.AGENCY_ADMIN.value, UserRole.MODEL.value])
async def get_financial_summary(
    model_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get financial summary for the agency or a specific model."""
    # Build filters
    transaction_filters = []
    payout_filters = []
    
    if model_id:
        # Verify access
        model = await verify_model_access(model_id, current_user, db)
        transaction_filters.append(Transaction.model_id == model_id)
        payout_filters.append(Payout.model_id == model_id)
    elif current_user.role == UserRole.MODEL:
        # Get model ID for current user
        model_stmt = select(Model.id).where(Model.user_id == current_user.id)
        user_model_id = await db.scalar(model_stmt)
        if user_model_id:
            transaction_filters.append(Transaction.model_id == user_model_id)
            payout_filters.append(Payout.model_id == user_model_id)
    elif current_user.agency_id:
        transaction_filters.append(Transaction.agency_id == current_user.agency_id)
        payout_filters.append(Payout.agency_id == current_user.agency_id)
    
    # Total revenue
    revenue_stmt = select(func.coalesce(func.sum(Transaction.gross_amount), 0)).where(
        and_(
            Transaction.status == TransactionStatus.COMPLETED,
            *transaction_filters
        )
    )
    total_revenue = await db.scalar(revenue_stmt) or Decimal('0')
    
    # Pending payouts
    pending_payouts_stmt = select(func.coalesce(func.sum(Payout.net_amount), 0)).where(
        and_(
            Payout.status == PayoutStatus.PENDING,
            *payout_filters
        )
    )
    pending_payouts = await db.scalar(pending_payouts_stmt) or Decimal('0')
    
    # Completed payouts
    completed_payouts_stmt = select(func.coalesce(func.sum(Payout.net_amount), 0)).where(
        and_(
            Payout.status == PayoutStatus.COMPLETED,
            *payout_filters
        )
    )
    completed_payouts = await db.scalar(completed_payouts_stmt) or Decimal('0')
    
    # Available balance (using pending_payout field from Model)
    if model_id:
        model_stmt = select(Model.pending_payout).where(Model.id == model_id)
        available_balance = await db.scalar(model_stmt) or Decimal('0')
    else:
        # Sum all model pending payouts in agency
        balance_stmt = select(func.coalesce(func.sum(Model.pending_payout), 0))
        if current_user.agency_id:
            balance_stmt = balance_stmt.where(Model.agency_id == current_user.agency_id)
        available_balance = await db.scalar(balance_stmt) or Decimal('0')
    
    # Current month revenue
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    month_revenue_stmt = select(func.coalesce(func.sum(Transaction.gross_amount), 0)).where(
        and_(
            Transaction.status == TransactionStatus.COMPLETED,
            Transaction.created_at >= month_start,
            *transaction_filters
        )
    )
    current_month_revenue = await db.scalar(month_revenue_stmt) or Decimal('0')
    
    # Last month revenue
    last_month_end = month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    last_month_revenue_stmt = select(func.coalesce(func.sum(Transaction.gross_amount), 0)).where(
        and_(
            Transaction.status == TransactionStatus.COMPLETED,
            Transaction.created_at >= last_month_start,
            Transaction.created_at < month_start,
            *transaction_filters
        )
    )
    last_month_revenue = await db.scalar(last_month_revenue_stmt) or Decimal('0')
    
    # Revenue by type
    revenue_by_type_stmt = select(
        Transaction.type,
        func.coalesce(func.sum(Transaction.gross_amount), 0).label('amount')
    ).where(
        and_(
            Transaction.status == TransactionStatus.COMPLETED,
            *transaction_filters
        )
    ).group_by(Transaction.type)
    
    revenue_by_type_result = await db.execute(revenue_by_type_stmt)
    revenue_by_type = {}
    for row in revenue_by_type_result:
        revenue_by_type[row[0].value] = row[1]
    
    # Recent transactions
    recent_trans_stmt = select(Transaction).where(
        and_(*transaction_filters)
    ).order_by(Transaction.created_at.desc()).limit(10)
    
    recent_trans_result = await db.execute(recent_trans_stmt)
    recent_transactions = []
    
    for trans in recent_trans_result.scalars():
        # Get model and user names
        model_stmt = select(Model).where(Model.id == trans.model_id)
        model = await db.scalar(model_stmt)
        
        user_stmt = select(User).where(User.id == trans.user_id)
        user = await db.scalar(user_stmt)
        
        recent_transactions.append(TransactionResponse(
            id=trans.id,
            model_id=trans.model_id,
            model_name=model.stage_name if model else "Unknown",
            user_id=trans.user_id,
            user_name=f"{user.first_name} {user.last_name}" if user else "Unknown",
            chat_id=trans.chat_id,
            content_id=trans.content_id,
            type=trans.type,
            status=trans.status,
            gross_amount=trans.gross_amount,
            platform_fee=trans.platform_fee,
            agency_fee=trans.agency_fee,
            model_earnings=trans.model_earnings,
            description=trans.description,
            payment_method=trans.payment_method,
            external_id=trans.external_id,
            metadata=trans.metadata or {},
            created_at=trans.created_at,
            completed_at=trans.completed_at
        ))
    
    return FinancialSummary(
        total_revenue=total_revenue,
        pending_payouts=pending_payouts,
        completed_payouts=completed_payouts,
        available_balance=available_balance,
        current_month_revenue=current_month_revenue,
        last_month_revenue=last_month_revenue,
        revenue_by_type=revenue_by_type,
        recent_transactions=recent_transactions
    )


@router.get("/invoices", response_model=List[InvoiceResponse])
@require_roles([UserRole.SUPER_ADMIN.value, UserRole.AGENCY_OWNER.value])
async def list_invoices(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List agency invoices."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Build query
    query = select(Invoice)
    
    if current_user.agency_id:
        query = query.where(Invoice.agency_id == current_user.agency_id)
    
    # Apply pagination
    offset = (page - 1) * limit
    query = query.order_by(Invoice.created_at.desc()).offset(offset).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    invoices = result.scalars().all()
    
    # Build response
    response = []
    for invoice in invoices:
        response.append(InvoiceResponse(
            id=invoice.id,
            agency_id=invoice.agency_id,
            invoice_number=invoice.invoice_number,
            period_start=invoice.period_start,
            period_end=invoice.period_end,
            total_amount=invoice.total_amount,
            status=invoice.status,
            due_date=invoice.due_date,
            paid_at=invoice.paid_at,
            items=invoice.items or [],
            created_at=invoice.created_at
        ))
    
    return response


# Commission endpoints
@router.get("/commission/tiers")
@require_admin()
async def get_commission_tiers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get commission tier structure."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return {
        "tiers": [
            {
                "threshold": 0,
                "rate": 0.20,
                "label": "$0 - $10,000"
            },
            {
                "threshold": 10000,
                "rate": 0.25,
                "label": "$10,000 - $25,000"
            },
            {
                "threshold": 25000,
                "rate": 0.30,
                "label": "$25,000 - $50,000"
            },
            {
                "threshold": 50000,
                "rate": 0.35,
                "label": "$50,000+"
            }
        ],
        "platform_fee": 0.20
    }


@router.get("/commission/model/{model_id}")
@require_model_assignment(model_id_param="model_id")
async def get_model_commission_info(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get commission information for a specific model."""
    # Verify access
    model = await verify_model_access(model_id, current_user, db)
    
    # Get commission service
    commission_service = CommissionService(db)
    
    # Get current month revenue
    monthly_revenue = await commission_service.get_model_monthly_revenue(model_id)
    
    # Get tier information
    tier_info = commission_service.get_tier_info(monthly_revenue)
    
    # Calculate sample commissions for different amounts
    sample_amounts = [Decimal("10"), Decimal("50"), Decimal("100"), Decimal("500")]
    sample_calculations = []
    
    for amount in sample_amounts:
        fees = commission_service.calculate_tiered_commission(amount, monthly_revenue)
        sample_calculations.append({
            "amount": float(amount),
            "platform_fee": float(fees["platform_fee"]),
            "agency_fee": float(fees["agency_fee"]),
            "model_earnings": float(fees["model_earnings"])
        })
    
    return {
        "model_id": model_id,
        "model_name": model.stage_name,
        "current_month_revenue": tier_info["monthly_revenue"],
        "current_tier": tier_info["current_tier"],
        "current_rate": tier_info["current_rate"],
        "next_tier": tier_info["next_tier"],
        "progress_to_next_tier": tier_info["progress_to_next"],
        "sample_calculations": sample_calculations
    }


@router.post("/commission/calculate")
@require_admin()
async def calculate_commission(
    model_id: int,
    amount: Decimal = Field(..., gt=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Calculate commission for a given amount and model."""
    # Verify access
    model = await verify_model_access(model_id, current_user, db)
    
    # Get commission service
    commission_service = CommissionService(db)
    
    # Calculate fees
    fees = await commission_service.calculate_transaction_fees(
        model_id=model_id,
        gross_amount=amount
    )
    
    # Get current tier info
    monthly_revenue = await commission_service.get_model_monthly_revenue(model_id)
    tier_info = commission_service.get_tier_info(monthly_revenue)
    
    return {
        "gross_amount": float(amount),
        "platform_fee": float(fees["platform_fee"]),
        "agency_fee": float(fees["agency_fee"]),
        "model_earnings": float(fees["model_earnings"]),
        "effective_agency_rate": float(fees["agency_fee"] / (amount - fees["platform_fee"])),
        "tier_info": tier_info
    }
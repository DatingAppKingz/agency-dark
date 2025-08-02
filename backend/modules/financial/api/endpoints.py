"""
Financial API endpoints for commission, payouts, and invoicing.
"""
import logging
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from core.database import get_db
from core.dependencies import get_current_user, RoleChecker
from core.domain.models import User, UserRole
from modules.financial.application.commission_service import CommissionService
from modules.financial.application.payout_service import PayoutService
from modules.financial.application.crypto_service import CryptoService
from modules.financial.application.invoice_service import InvoiceService
from modules.financial.application.billing_service import BillingService
from modules.financial.domain.schemas import (
    # Commission
    CommissionRuleCreate,
    CommissionRuleUpdate,
    CommissionRuleResponse,
    CommissionOverrideRequest,
    CommissionCalculation,
    CommissionAdjustmentCreate,
    CommissionAdjustmentResponse,
    CommissionReport,
    CommissionReportFilter,
    # Billing
    BillingCycleSummary,
    BillingCycleDetails,
    # Payouts
    PayoutRequest,
    PayoutResponse,
    PayoutStatus,
    PayoutScheduleCreate,
    PayoutScheduleResponse,
    PayoutBatchResponse,
    PayoutApprovalRequest,
    # Crypto
    CryptoWalletCreate,
    CryptoWalletResponse,
    CryptoWalletVerification,
    CryptoNetwork,
    # Invoices
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoiceStatus,
    # Transactions
    TransactionFilter,
    TransactionResponse,
    FinancialSummary
)


router = APIRouter(prefix="/financial", tags=["financial"])

# Include transaction endpoints
from .transaction_endpoints import router as transaction_router
router.include_router(transaction_router)


# Commission endpoints
@router.post("/commission/rules", response_model=CommissionRuleResponse)
async def create_commission_rule(
    rule_data: CommissionRuleCreate,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new commission rule.
    
    - **SUPER_ADMIN**: Can create rules for any agency
    - **AGENCY_OWNER**: Can create rules for their own agency
    """
    # Verify permissions
    if current_user.role == UserRole.AGENCY_OWNER:
        if str(current_user.agency_id) != rule_data.agency_id:
            raise HTTPException(
                status_code=403,
                detail="Can only create rules for your own agency"
            )
    
    service = CommissionService(db)
    
    try:
        rule = await service.create_commission_rule(rule_data, current_user)
        return rule
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/commission/rules/{rule_id}", response_model=CommissionRuleResponse)
async def update_commission_rule(
    rule_id: str,
    update_data: CommissionRuleUpdate,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Update an existing commission rule."""
    service = CommissionService(db)
    
    try:
        # Get rule to check permissions
        rules = await service.get_commission_rules(include_historical=True)
        rule = next((r for r in rules if str(r.id) == rule_id), None)
        
        if not rule:
            raise HTTPException(status_code=404, detail="Commission rule not found")
        
        # Check permissions
        if current_user.role == UserRole.AGENCY_OWNER:
            if str(current_user.agency_id) != rule.agency_id:
                raise HTTPException(status_code=403, detail="Not authorized")
        
        updated_rule = await service.update_commission_rule(
            rule_id,
            update_data,
            current_user
        )
        return updated_rule
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/commission/override", response_model=CommissionRuleResponse)
async def override_commission(
    agency_id: str = Query(...),
    model_id: Optional[str] = Query(None),
    override_data: CommissionOverrideRequest = ...,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(RoleChecker([UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """
    Override commission for an agency or model (SUPER_ADMIN only).
    """
    service = CommissionService(db)
    
    try:
        rule = await service.override_commission(
            agency_id,
            model_id,
            override_data,
            current_user
        )
        return rule
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/commission/rules", response_model=List[CommissionRuleResponse])
async def get_commission_rules(
    agency_id: Optional[str] = Query(None),
    model_id: Optional[str] = Query(None),
    include_historical: bool = Query(False),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Get commission rules with optional filters."""
    # Apply permission filters
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.role == UserRole.AGENCY_OWNER:
            agency_id = str(current_user.agency_id)
        elif current_user.role == UserRole.MODEL:
            # Models can only see their own rules
            from sqlalchemy import select
            from core.domain.models import ModelProfile
            
            result = await db.execute(
                select(ModelProfile).where(ModelProfile.user_id == current_user.id)
            )
            model_profile = result.scalar_one_or_none()
            if model_profile:
                model_id = str(model_profile.id)
                agency_id = str(model_profile.agency_id)
            else:
                return []
        elif current_user.role == UserRole.MEMBER:
            agency_id = str(current_user.agency_id)
    
    service = CommissionService(db)
    rules = await service.get_commission_rules(
        agency_id=agency_id,
        model_id=model_id,
        include_historical=include_historical
    )
    
    return rules


@router.post("/commission/calculate", response_model=CommissionCalculation)
async def calculate_commission(
    gross_amount: Decimal = Query(..., gt=0),
    model_id: str = Query(...),
    calculation_date: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.MEMBER,
            UserRole.MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Calculate commission for a given amount and model."""
    service = CommissionService(db)
    
    try:
        calculation = await service.calculate_commission(
            gross_amount,
            model_id,
            calculation_date
        )
        return calculation
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/commission/calculate-tiered", response_model=CommissionCalculation)
async def calculate_tiered_commission(
    gross_amount: Decimal = Query(..., gt=0),
    model_id: str = Query(...),
    total_revenue: Optional[Decimal] = Query(None),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Calculate commission with automatic tier upgrades based on revenue."""
    service = CommissionService(db)
    
    try:
        calculation = await service.calculate_tiered_commission(
            gross_amount,
            model_id,
            total_revenue
        )
        return calculation
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/commission/bulk-calculate", response_model=List[CommissionCalculation])
async def bulk_calculate_commission(
    billing_cycle_id: str,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Calculate commission for all transactions in a billing cycle."""
    service = CommissionService(db)
    
    try:
        calculations = await service.bulk_calculate_commission(billing_cycle_id)
        return calculations
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/commission/adjustments", response_model=CommissionAdjustmentResponse)
async def create_commission_adjustment(
    adjustment_data: CommissionAdjustmentCreate,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Create a commission adjustment (credit or debit)."""
    service = CommissionService(db)
    
    try:
        adjustment = await service.create_commission_adjustment(
            adjustment_data,
            current_user
        )
        return adjustment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/commission/report", response_model=CommissionReport)
async def generate_commission_report(
    filter_params: CommissionReportFilter,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Generate a detailed commission report."""
    service = CommissionService(db)
    
    try:
        # Apply permission filters
        if current_user.role != UserRole.SUPER_ADMIN:
            filter_params.agency_id = str(current_user.agency_id)
        
        report = await service.generate_commission_report(
            filter_params,
            current_user
        )
        return report
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Billing cycle endpoints
@router.post("/billing-cycles", response_model=BillingCycleSummary)
async def create_billing_cycle(
    agency_id: str = Query(...),
    cycle_start: datetime = Query(...),
    cycle_end: datetime = Query(...),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Create a new billing cycle."""
    # Check permissions
    if current_user.role == UserRole.AGENCY_OWNER:
        if str(current_user.agency_id) != agency_id:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    service = BillingService(db)
    
    try:
        cycle = await service.create_billing_cycle(
            agency_id,
            cycle_start,
            cycle_end
        )
        return cycle
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/billing-cycles/{cycle_id}/close", response_model=BillingCycleDetails)
async def close_billing_cycle(
    cycle_id: str,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.MEMBER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Close a billing cycle and calculate final amounts."""
    service = BillingService(db)
    
    try:
        # Get cycle to check permissions
        cycles = await service.get_billing_cycles()
        cycle = next((c for c in cycles if str(c.id) == cycle_id), None)
        
        if not cycle:
            raise HTTPException(status_code=404, detail="Billing cycle not found")
        
        # Check permissions
        if current_user.role in [UserRole.AGENCY_OWNER, UserRole.MEMBER]:
            if str(current_user.agency_id) != cycle.agency_id:
                raise HTTPException(status_code=403, detail="Not authorized")
        
        closed_cycle = await service.close_billing_cycle(cycle_id, current_user)
        return closed_cycle
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/billing-cycles", response_model=List[BillingCycleSummary])
async def get_billing_cycles(
    agency_id: Optional[str] = Query(None),
    include_open: bool = Query(True),
    include_closed: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.MEMBER,
            UserRole.MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Get billing cycles with optional filters."""
    # Apply permission filters
    if current_user.role != UserRole.SUPER_ADMIN:
        agency_id = str(current_user.agency_id)
    
    service = BillingService(db)
    cycles = await service.get_billing_cycles(
        agency_id=agency_id,
        include_open=include_open,
        include_closed=include_closed,
        limit=limit,
        offset=offset
    )
    
    return cycles


# Payout endpoints
@router.post("/payouts", response_model=PayoutResponse)
async def create_payout(
    payout_data: PayoutRequest,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.MEMBER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Create a new payout."""
    service = PayoutService(db)
    
    try:
        payout = await service.create_payout(payout_data, current_user)
        return payout
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/payouts/{payout_id}/process", response_model=PayoutResponse)
async def process_payout(
    payout_id: str,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Process a pending payout."""
    service = PayoutService(db)
    
    try:
        payout = await service.process_payout(payout_id)
        return payout
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/payouts", response_model=List[PayoutResponse])
async def get_payouts(
    billing_cycle_id: Optional[str] = Query(None),
    recipient_id: Optional[str] = Query(None),
    status: Optional[PayoutStatus] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Get payouts with optional filters."""
    # Apply permission filters
    if current_user.role == UserRole.MODEL:
        recipient_id = str(current_user.id)
    elif current_user.role in [UserRole.AGENCY_OWNER, UserRole.MEMBER]:
        # TODO: Filter by agency
        pass
    
    service = PayoutService(db)
    payouts = await service.get_payouts(
        billing_cycle_id=billing_cycle_id,
        recipient_id=recipient_id,
        status=status,
        limit=limit,
        offset=offset
    )
    
    return payouts


@router.post("/payouts/schedules", response_model=PayoutScheduleResponse)
async def create_payout_schedule(
    schedule_data: PayoutScheduleCreate,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.MEMBER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Create automatic payout schedule for a recipient."""
    service = PayoutService(db)
    
    try:
        schedule = await service.create_payout_schedule(schedule_data, current_user)
        return schedule
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/payouts/batch/process", response_model=PayoutBatchResponse)
async def process_scheduled_payouts_batch(
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Process all scheduled payouts in batch (super admin only)."""
    service = PayoutService(db)
    
    try:
        result = await service.process_scheduled_payouts_batch()
        return result
    except Exception as e:
        logger.error(f"Batch payout processing failed: {e}")
        raise HTTPException(status_code=500, detail="Batch processing failed")


@router.post("/payouts/retry-failed")
async def retry_failed_payouts(
    max_age_hours: int = Query(24, ge=1, le=168),  # Max 1 week
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Retry failed payouts within specified age."""
    service = PayoutService(db)
    
    try:
        result = await service.retry_failed_payouts(max_age_hours)
        return result
    except Exception as e:
        logger.error(f"Failed payout retry failed: {e}")
        raise HTTPException(status_code=500, detail="Retry processing failed")


@router.post("/payouts/{payout_id}/approve", response_model=PayoutResponse)
async def approve_payout(
    payout_id: str,
    approval: PayoutApprovalRequest,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Approve or reject a pending payout."""
    service = PayoutService(db)
    
    try:
        payout = await service.approve_payout(payout_id, approval, current_user)
        return payout
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/payouts/schedules", response_model=List[PayoutScheduleResponse])
async def get_payout_schedules(
    recipient_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Get payout schedules with optional filters."""
    # Apply permission filters
    if current_user.role == UserRole.MODEL:
        recipient_id = str(current_user.id)
    
    from modules.financial.domain.models import PayoutSchedule
    from sqlalchemy import select, and_
    
    query = select(PayoutSchedule)
    
    conditions = []
    if recipient_id:
        conditions.append(PayoutSchedule.recipient_id == recipient_id)
    if is_active is not None:
        conditions.append(PayoutSchedule.is_active == is_active)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    result = await db.execute(query)
    schedules = result.scalars().all()
    
    return [PayoutScheduleResponse.model_validate(s) for s in schedules]


@router.put("/payouts/schedules/{schedule_id}/pause")
async def pause_payout_schedule(
    schedule_id: str,
    reason: str = Query(..., min_length=10),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Pause an active payout schedule."""
    from modules.financial.domain.models import PayoutSchedule
    
    schedule = await db.get(PayoutSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    if not schedule.is_active:
        raise HTTPException(status_code=400, detail="Schedule is already inactive")
    
    schedule.is_active = False
    schedule.paused_at = datetime.utcnow()
    schedule.paused_reason = reason
    
    await db.commit()
    
    return {"status": "paused", "schedule_id": schedule_id}


# Crypto wallet endpoints
@router.post("/wallets", response_model=CryptoWalletResponse)
async def create_wallet(
    wallet_data: CryptoWalletCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new crypto wallet."""
    service = CryptoService(db)
    
    try:
        wallet = await service.create_wallet(current_user, wallet_data)
        return wallet
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/wallets/{wallet_id}/verify", response_model=CryptoWalletResponse)
async def verify_wallet(
    wallet_id: str,
    verification: CryptoWalletVerification,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify ownership of a crypto wallet."""
    service = CryptoService(db)
    
    try:
        wallet = await service.verify_wallet(wallet_id, current_user, verification)
        return wallet
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/wallets", response_model=List[CryptoWalletResponse])
async def get_wallets(
    network: Optional[CryptoNetwork] = Query(None),
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's crypto wallets."""
    service = CryptoService(db)
    wallets = await service.get_user_wallets(
        current_user,
        network=network,
        active_only=active_only
    )
    
    return wallets


# Invoice endpoints
@router.post("/invoices", response_model=InvoiceResponse)
async def create_invoice(
    invoice_data: InvoiceCreate,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.MEMBER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Create a new invoice."""
    service = InvoiceService(db)
    
    try:
        invoice = await service.create_invoice(invoice_data, current_user)
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: str,
    update_data: InvoiceUpdate,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.MEMBER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Update an invoice."""
    service = InvoiceService(db)
    
    try:
        invoice = await service.update_invoice(invoice_id, update_data, current_user)
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/invoices/{invoice_id}/send", response_model=InvoiceResponse)
async def send_invoice(
    invoice_id: str,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.MEMBER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Send an invoice to the recipient."""
    service = InvoiceService(db)
    
    try:
        invoice = await service.send_invoice(invoice_id, current_user)
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/invoices", response_model=List[InvoiceResponse])
async def get_invoices(
    agency_id: Optional[str] = Query(None),
    model_id: Optional[str] = Query(None),
    status: Optional[InvoiceStatus] = Query(None),
    due_date_start: Optional[date] = Query(None),
    due_date_end: Optional[date] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.MODEL,
            UserRole.MEMBER,
            UserRole.MEMBER
        ])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Get invoices with optional filters."""
    # Apply permission filters
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.role == UserRole.MODEL:
            # Get model profile
            from sqlalchemy import select
            from core.domain.models import ModelProfile
            
            result = await db.execute(
                select(ModelProfile).where(ModelProfile.user_id == current_user.id)
            )
            model_profile = result.scalar_one_or_none()
            if model_profile:
                model_id = str(model_profile.id)
                agency_id = str(model_profile.agency_id)
        else:
            agency_id = str(current_user.agency_id)
    
    service = InvoiceService(db)
    
    # Convert dates to datetime
    due_start = datetime.combine(due_date_start, datetime.min.time()) if due_date_start else None
    due_end = datetime.combine(due_date_end, datetime.max.time()) if due_date_end else None
    
    invoices = await service.get_invoices(
        agency_id=agency_id,
        model_id=model_id,
        status=status,
        due_date_start=due_start,
        due_date_end=due_end,
        limit=limit,
        offset=offset
    )
    
    return invoices


@router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Download invoice PDF."""
    # In production, this would generate or retrieve the PDF
    # For now, return a placeholder response
    
    return Response(
        content=b"PDF content would be here",
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=invoice_{invoice_id}.pdf"
        }
    )


# Payment gateway endpoints
@router.post("/payment-gateways", response_model=PaymentGatewayConfigResponse)
async def create_payment_gateway(
    config_data: PaymentGatewayConfigCreate,
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Create payment gateway configuration (super admin only)."""
    from modules.financial.application.payment_gateway_service import PaymentGatewayService
    service = PaymentGatewayService(db)
    
    try:
        config = await service.create_gateway_config(config_data)
        return config
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/payment-gateways", response_model=List[PaymentGatewayConfigResponse])
async def get_payment_gateways(
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Get active payment gateway configurations."""
    from modules.financial.application.payment_gateway_service import PaymentGatewayService
    service = PaymentGatewayService(db)
    
    agency_id = None
    if current_user.role == UserRole.AGENCY_OWNER:
        agency_id = str(current_user.agency_id)
    
    configs = await service.get_active_configs(agency_id)
    return configs


@router.post("/payments/crypto", response_model=CryptoPaymentResponse)
async def create_crypto_payment(
    payment_request: CryptoPaymentRequest,
    provider: str = Query(..., description="Payment provider (coinbase_commerce, bitpay)"),
    current_user: User = Depends(get_current_user),
    role_checker: RoleChecker = Depends(
        RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.MEMBER])
    ),
    db: AsyncSession = Depends(get_db)
):
    """Create a crypto payment request."""
    from modules.financial.application.payment_gateway_service import PaymentGatewayService
    service = PaymentGatewayService(db)
    
    try:
        agency_id = str(current_user.agency_id) if current_user.agency_id else None
        payment = await service.create_payment(payment_request, provider, agency_id)
        return payment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Webhook endpoints
@router.post("/webhooks/{provider}")
async def handle_payment_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle payment webhooks from crypto providers."""
    from modules.financial.application.payment_gateway_service import PaymentGatewayService
    service = PaymentGatewayService(db)
    
    # Get raw body for signature verification
    body = await request.body()
    headers = dict(request.headers)
    
    try:
        result = await service.process_webhook(provider, headers, body)
        
        if result['success']:
            return {"status": "ok"}
        else:
            raise HTTPException(status_code=400, detail=result.get('error'))
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")
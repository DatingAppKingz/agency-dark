"""
Commission management API endpoints.

Provides endpoints for calculating commissions, managing commission rules,
and generating commission reports.
"""
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_current_user, require_roles
from core.domain.models import User
from modules.financial.application.commission_calculator import CommissionCalculator
from modules.financial.domain.schemas import (
    CommissionRuleCreate,
    CommissionRuleUpdate,
    CommissionRuleResponse,
    CommissionOverrideRequest,
    CommissionCalculation,
    CommissionReport,
    CommissionReportFilter,
    CommissionAdjustmentCreate
)


router = APIRouter(prefix="/api/v1/financial/commissions", tags=["financial-commissions"])


@router.post("/calculate", response_model=CommissionCalculation)
async def calculate_commission(
    gross_amount: Decimal = Query(..., gt=0, description="Gross revenue amount"),
    agency_id: UUID = Query(..., description="Agency ID"),
    model_id: Optional[UUID] = Query(None, description="Model ID for specific rules"),
    calculation_date: Optional[datetime] = Query(None, description="Date for calculation"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate commission for a given amount.
    
    Returns the commission breakdown including rates and amounts.
    """
    # Verify user has access to this agency
    if current_user.role != "super_admin" and str(current_user.agency_id) != str(agency_id):
        raise HTTPException(status_code=403, detail="Access denied to this agency")
    
    calculator = CommissionCalculator(db)
    
    try:
        calculation = await calculator.calculate_commission(
            gross_amount=gross_amount,
            agency_id=agency_id,
            model_id=model_id,
            calculation_date=calculation_date
        )
        return calculation
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rules", response_model=CommissionRuleResponse)
async def create_commission_rule(
    rule_data: CommissionRuleCreate,
    current_user: User = Depends(require_roles(["super_admin", "agency_owner"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new commission rule.
    
    Requires agency_owner or super_admin role.
    """
    # Verify agency access
    if current_user.role != "super_admin":
        if str(current_user.agency_id) != rule_data.agency_id:
            raise HTTPException(status_code=403, detail="Cannot create rules for other agencies")
    
    calculator = CommissionCalculator(db)
    
    try:
        rule = await calculator.create_commission_rule(
            rule_data=rule_data,
            created_by_id=current_user.id
        )
        return rule
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rules", response_model=List[CommissionRuleResponse])
async def list_commission_rules(
    agency_id: Optional[UUID] = Query(None, description="Filter by agency"),
    model_id: Optional[UUID] = Query(None, description="Filter by model"),
    active_only: bool = Query(True, description="Show only active rules"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List commission rules with filtering.
    
    Non-super admins can only see rules for their agency.
    """
    # Apply agency filter for non-super admins
    if current_user.role != "super_admin":
        agency_id = current_user.agency_id
    
    calculator = CommissionCalculator(db)
    
    offset = (page - 1) * page_size
    rules = await calculator.list_commission_rules(
        agency_id=agency_id,
        model_id=model_id,
        active_only=active_only,
        limit=page_size,
        offset=offset
    )
    
    return rules


@router.get("/rules/{rule_id}", response_model=CommissionRuleResponse)
async def get_commission_rule(
    rule_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific commission rule."""
    calculator = CommissionCalculator(db)
    
    rule = await calculator.get_commission_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Commission rule not found")
    
    # Verify access
    if current_user.role != "super_admin" and rule.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return CommissionRuleResponse.from_orm(rule)


@router.patch("/rules/{rule_id}", response_model=CommissionRuleResponse)
async def update_commission_rule(
    rule_id: UUID,
    update_data: CommissionRuleUpdate,
    current_user: User = Depends(require_roles(["super_admin", "agency_owner"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a commission rule.
    
    Only certain fields can be updated.
    """
    calculator = CommissionCalculator(db)
    
    # Get rule to verify access
    rule = await calculator.get_commission_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Commission rule not found")
    
    # Verify access
    if current_user.role != "super_admin" and rule.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        updated_rule = await calculator.update_commission_rule(
            rule_id=rule_id,
            update_data=update_data,
            updated_by_id=current_user.id
        )
        return updated_rule
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/override", response_model=CommissionRuleResponse)
async def override_commission(
    agency_id: UUID = Body(..., description="Agency ID"),
    model_id: Optional[UUID] = Body(None, description="Model ID for model-specific override"),
    override_request: CommissionOverrideRequest = Body(...),
    current_user: User = Depends(require_roles(["super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a commission override.
    
    This creates a new rule that overrides existing rules.
    Requires super_admin role.
    """
    calculator = CommissionCalculator(db)
    
    try:
        override_rule = await calculator.override_commission(
            agency_id=agency_id,
            model_id=model_id,
            override_request=override_request,
            override_by_id=current_user.id
        )
        return override_rule
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reports/generate", response_model=CommissionReport)
async def generate_commission_report(
    filter_params: CommissionReportFilter,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a detailed commission report.
    
    Provides breakdown by model, tier distribution, and totals.
    """
    # Apply agency filter for non-super admins
    if current_user.role != "super_admin":
        filter_params.agency_id = str(current_user.agency_id)
    
    calculator = CommissionCalculator(db)
    
    try:
        report = await calculator.generate_commission_report(
            filter_params=filter_params,
            generated_by_id=current_user.id
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/adjustments", response_model=dict)
async def create_commission_adjustment(
    adjustment_data: CommissionAdjustmentCreate,
    current_user: User = Depends(require_roles(["super_admin", "agency_owner"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a commission adjustment.
    
    Used for corrections, bonuses, or penalties.
    """
    # Verify agency access
    if current_user.role != "super_admin":
        if adjustment_data.agency_id != str(current_user.agency_id):
            raise HTTPException(status_code=403, detail="Cannot create adjustments for other agencies")
    
    calculator = CommissionCalculator(db)
    
    try:
        adjustment = await calculator.create_commission_adjustment(
            adjustment_data=adjustment_data,
            created_by_id=current_user.id
        )
        
        return {
            "transaction_id": str(adjustment.id),
            "amount": float(adjustment.amount),
            "type": adjustment.type,
            "description": adjustment.description,
            "created_at": adjustment.created_at
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tiers")
async def get_commission_tiers(
    current_user: User = Depends(get_current_user)
):
    """
    Get available commission tiers and their default rates.
    """
    from modules.financial.domain.models import CommissionTier
    
    tiers = {
        CommissionTier.TIER_1: {
            "name": "Tier 1",
            "model_rate": 70,
            "agency_rate": 30,
            "description": "Standard tier - 70% to model, 30% to agency"
        },
        CommissionTier.TIER_2: {
            "name": "Tier 2",
            "model_rate": 65,
            "agency_rate": 35,
            "description": "Enhanced tier - 65% to model, 35% to agency"
        },
        CommissionTier.TIER_3: {
            "name": "Tier 3",
            "model_rate": 60,
            "agency_rate": 40,
            "description": "Premium tier - 60% to model, 40% to agency"
        },
        CommissionTier.CUSTOM: {
            "name": "Custom",
            "model_rate": None,
            "agency_rate": None,
            "description": "Custom rates - set your own percentages"
        }
    }
    
    return tiers


@router.post("/preview")
async def preview_commission_changes(
    rule_data: CommissionRuleCreate,
    sample_amounts: List[Decimal] = Body(..., description="Sample amounts to preview"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Preview commission calculations with a new rule.
    
    Helps understand the impact before creating the rule.
    """
    # Verify agency access
    if current_user.role != "super_admin":
        if rule_data.agency_id != str(current_user.agency_id):
            raise HTTPException(status_code=403, detail="Access denied")
    
    calculator = CommissionCalculator(db)
    
    # Calculate with proposed rule
    previews = []
    for amount in sample_amounts:
        # Calculate with current rules
        current = await calculator.calculate_commission(
            gross_amount=amount,
            agency_id=UUID(rule_data.agency_id),
            model_id=UUID(rule_data.model_id) if rule_data.model_id else None
        )
        
        # Calculate with proposed rule
        if rule_data.tier == "custom":
            proposed_model_rate = rule_data.rate
        else:
            proposed_model_rate = CommissionCalculator.TIER_RATES[rule_data.tier]
        
        proposed_agency_rate = Decimal("100") - proposed_model_rate
        proposed_agency_amount = (amount * proposed_agency_rate / Decimal("100")).quantize(
            Decimal("0.01")
        )
        proposed_model_amount = amount - proposed_agency_amount
        
        previews.append({
            "gross_amount": float(amount),
            "current": {
                "agency_amount": float(current.commission_amount),
                "model_amount": float(current.net_amount),
                "agency_rate": float(current.commission_rate)
            },
            "proposed": {
                "agency_amount": float(proposed_agency_amount),
                "model_amount": float(proposed_model_amount),
                "agency_rate": float(proposed_agency_rate)
            },
            "difference": {
                "agency_amount": float(proposed_agency_amount - current.commission_amount),
                "model_amount": float(proposed_model_amount - current.net_amount)
            }
        })
    
    return {
        "rule_summary": {
            "tier": rule_data.tier,
            "rate": float(rule_data.rate) if rule_data.rate else None,
            "effective_from": rule_data.effective_from,
            "effective_until": rule_data.effective_until
        },
        "previews": previews
    }
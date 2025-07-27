"""
Commission calculation service.

Handles all commission calculations including tiered rates, overrides,
and adjustments with full audit trail.
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.exc import IntegrityError

from core.exceptions import ValidationError, BusinessLogicError
from core.events import EventBus, Event
from modules.analytics.domain.models import AnalyticsEvent

from ..domain.models import (
    CommissionRule,
    CommissionTier,
    FinancialTransaction,
    TransactionType,
    TransactionStatus,
    BillingCycle
)
from ..domain.schemas import (
    CommissionCalculation,
    CommissionRuleCreate,
    CommissionRuleUpdate,
    CommissionRuleResponse,
    CommissionOverrideRequest,
    CommissionReport,
    CommissionReportFilter,
    CommissionAdjustmentCreate
)
from .transaction_service import TransactionService


logger = logging.getLogger(__name__)


class CommissionCalculator:
    """Service for calculating and managing commissions."""
    
    # Default commission rates by tier
    TIER_RATES = {
        CommissionTier.TIER_1: Decimal("70.00"),  # 70% to model
        CommissionTier.TIER_2: Decimal("65.00"),  # 65% to model
        CommissionTier.TIER_3: Decimal("60.00"),  # 60% to model
        CommissionTier.CUSTOM: None  # Use custom rate
    }
    
    def __init__(self, db: AsyncSession, event_bus: Optional[EventBus] = None):
        self.db = db
        self.event_bus = event_bus or EventBus()
        self.transaction_service = TransactionService(db, event_bus)
        
    async def calculate_commission(
        self,
        gross_amount: Decimal,
        agency_id: UUID,
        model_id: Optional[UUID] = None,
        calculation_date: Optional[datetime] = None
    ) -> CommissionCalculation:
        """
        Calculate commission for a given amount.
        
        Args:
            gross_amount: Gross revenue amount
            agency_id: Agency ID
            model_id: Optional model ID for model-specific rules
            calculation_date: Date for calculation (default: now)
            
        Returns:
            Commission calculation details
        """
        if gross_amount <= 0:
            raise ValidationError("Gross amount must be positive")
            
        calculation_date = calculation_date or datetime.utcnow()
        
        # Get applicable commission rule
        rule = await self._get_applicable_rule(agency_id, model_id, calculation_date)
        
        if not rule:
            # Use default tier 1 rate if no rule exists
            logger.warning(f"No commission rule found for agency {agency_id}, using default")
            commission_rate = self.TIER_RATES[CommissionTier.TIER_1]
            tier = CommissionTier.TIER_1
            is_override = False
        else:
            commission_rate = rule.rate
            tier = rule.tier
            is_override = rule.is_override
            
        # Calculate amounts
        model_rate = commission_rate
        agency_rate = Decimal("100.00") - model_rate
        
        model_amount = (gross_amount * model_rate / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        agency_amount = gross_amount - model_amount
        
        return CommissionCalculation(
            gross_amount=gross_amount,
            commission_rate=agency_rate,  # Agency's commission rate
            commission_amount=agency_amount,  # Agency's commission
            net_amount=model_amount,  # Model's earnings
            tier=tier,
            is_override=is_override,
            calculation_date=calculation_date
        )
        
    async def create_commission_rule(
        self,
        rule_data: CommissionRuleCreate,
        created_by_id: UUID
    ) -> CommissionRuleResponse:
        """
        Create a new commission rule.
        
        Args:
            rule_data: Rule creation data
            created_by_id: User creating the rule
            
        Returns:
            Created commission rule
        """
        # Validate rate based on tier
        if rule_data.tier == CommissionTier.CUSTOM:
            if not rule_data.rate:
                raise ValidationError("Custom tier requires a rate")
        else:
            # Use predefined rate for standard tiers
            rule_data.rate = self.TIER_RATES[rule_data.tier]
            
        # Check for overlapping rules
        overlapping = await self._check_overlapping_rules(
            rule_data.agency_id,
            rule_data.model_id,
            rule_data.effective_from,
            rule_data.effective_until
        )
        
        if overlapping:
            raise BusinessLogicError(
                "Commission rule overlaps with existing rule. "
                "Please adjust the effective dates."
            )
            
        # Create rule
        rule = CommissionRule(
            agency_id=UUID(rule_data.agency_id),
            model_id=UUID(rule_data.model_id) if rule_data.model_id else None,
            tier=rule_data.tier,
            rate=rule_data.rate,
            effective_from=rule_data.effective_from or datetime.utcnow(),
            effective_until=rule_data.effective_until
        )
        
        self.db.add(rule)
        
        try:
            await self.db.commit()
            await self.db.refresh(rule)
        except IntegrityError as e:
            await self.db.rollback()
            raise ValidationError(f"Failed to create commission rule: {str(e)}")
            
        # Emit event
        await self._emit_commission_event(rule, "created", created_by_id)
        
        logger.info(
            f"Commission rule {rule.id} created for agency {rule.agency_id}"
            f"{f' model {rule.model_id}' if rule.model_id else ''}"
        )
        
        return CommissionRuleResponse.from_orm(rule)
        
    async def update_commission_rule(
        self,
        rule_id: UUID,
        update_data: CommissionRuleUpdate,
        updated_by_id: UUID
    ) -> CommissionRuleResponse:
        """Update an existing commission rule."""
        rule = await self.get_commission_rule(rule_id)
        if not rule:
            raise ValidationError(f"Commission rule {rule_id} not found")
            
        # Update allowed fields
        if update_data.tier is not None:
            rule.tier = update_data.tier
            if update_data.tier != CommissionTier.CUSTOM:
                rule.rate = self.TIER_RATES[update_data.tier]
                
        if update_data.rate is not None and rule.tier == CommissionTier.CUSTOM:
            rule.rate = update_data.rate
            
        if update_data.effective_until is not None:
            rule.effective_until = update_data.effective_until
            
        await self.db.commit()
        await self.db.refresh(rule)
        
        # Emit event
        await self._emit_commission_event(rule, "updated", updated_by_id)
        
        return CommissionRuleResponse.from_orm(rule)
        
    async def override_commission(
        self,
        agency_id: UUID,
        model_id: Optional[UUID],
        override_request: CommissionOverrideRequest,
        override_by_id: UUID
    ) -> CommissionRuleResponse:
        """
        Create a commission override (super_admin only).
        
        This creates a new rule with override flag set.
        """
        # End any existing rules
        await self._end_existing_rules(
            agency_id,
            model_id,
            override_request.effective_from or datetime.utcnow()
        )
        
        # Create override rule
        rule = CommissionRule(
            agency_id=agency_id,
            model_id=model_id,
            tier=CommissionTier.CUSTOM,
            rate=override_request.rate,
            is_override=True,
            override_reason=override_request.reason,
            override_by=override_by_id,
            override_at=datetime.utcnow(),
            effective_from=override_request.effective_from or datetime.utcnow(),
            effective_until=override_request.effective_until
        )
        
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        
        # Emit event
        await self._emit_commission_event(rule, "overridden", override_by_id)
        
        logger.info(
            f"Commission override created for agency {agency_id}"
            f"{f' model {model_id}' if model_id else ''} by user {override_by_id}"
        )
        
        return CommissionRuleResponse.from_orm(rule)
        
    async def get_commission_rule(self, rule_id: UUID) -> Optional[CommissionRule]:
        """Get a commission rule by ID."""
        result = await self.db.execute(
            select(CommissionRule).where(CommissionRule.id == rule_id)
        )
        return result.scalar_one_or_none()
        
    async def list_commission_rules(
        self,
        agency_id: Optional[UUID] = None,
        model_id: Optional[UUID] = None,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0
    ) -> List[CommissionRuleResponse]:
        """List commission rules with filtering."""
        query = select(CommissionRule)
        
        conditions = []
        if agency_id:
            conditions.append(CommissionRule.agency_id == agency_id)
            
        if model_id:
            conditions.append(CommissionRule.model_id == model_id)
            
        if active_only:
            now = datetime.utcnow()
            conditions.append(
                and_(
                    CommissionRule.effective_from <= now,
                    or_(
                        CommissionRule.effective_until.is_(None),
                        CommissionRule.effective_until >= now
                    )
                )
            )
            
        if conditions:
            query = query.where(and_(*conditions))
            
        query = query.order_by(
            desc(CommissionRule.effective_from),
            CommissionRule.model_id.desc()  # Model-specific rules first
        )
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        rules = result.scalars().all()
        
        return [CommissionRuleResponse.from_orm(rule) for rule in rules]
        
    async def calculate_and_create_commission_transaction(
        self,
        revenue_transaction: FinancialTransaction,
        billing_cycle_id: Optional[UUID] = None,
        created_by_id: Optional[UUID] = None
    ) -> FinancialTransaction:
        """
        Calculate commission for a revenue transaction and create commission transaction.
        
        Args:
            revenue_transaction: The revenue transaction to calculate commission for
            billing_cycle_id: Optional billing cycle ID
            created_by_id: User creating the transaction
            
        Returns:
            Created commission transaction
        """
        if revenue_transaction.type != TransactionType.REVENUE:
            raise ValidationError("Can only calculate commission for revenue transactions")
            
        if not revenue_transaction.agency_id:
            raise ValidationError("Revenue transaction must have agency_id")
            
        # Calculate commission
        calculation = await self.calculate_commission(
            revenue_transaction.amount,
            revenue_transaction.agency_id,
            revenue_transaction.model_id,
            revenue_transaction.transaction_date
        )
        
        # Create commission transaction
        from ..domain.schemas import TransactionCreate
        
        commission_data = TransactionCreate(
            agency_id=str(revenue_transaction.agency_id),
            model_id=str(revenue_transaction.model_id) if revenue_transaction.model_id else None,
            type=TransactionType.COMMISSION,
            amount=calculation.commission_amount,
            currency=revenue_transaction.currency,
            billing_cycle_id=str(billing_cycle_id) if billing_cycle_id else None,
            description=f"Commission on revenue transaction {revenue_transaction.id}",
            external_reference=f"COMM_{revenue_transaction.id}",
            transaction_date=revenue_transaction.transaction_date,
            metadata={
                "revenue_transaction_id": str(revenue_transaction.id),
                "commission_rate": float(calculation.commission_rate),
                "tier": calculation.tier,
                "is_override": calculation.is_override
            }
        )
        
        commission_transaction = await self.transaction_service.create_transaction(
            commission_data,
            created_by_id or revenue_transaction.created_by_id
        )
        
        # Update revenue transaction with commission info
        revenue_transaction.commission_rate = calculation.commission_rate
        revenue_transaction.commission_amount = calculation.commission_amount
        await self.db.commit()
        
        return commission_transaction
        
    async def generate_commission_report(
        self,
        filter_params: CommissionReportFilter,
        generated_by_id: UUID
    ) -> CommissionReport:
        """Generate a detailed commission report."""
        # Base query for transactions
        query = select(FinancialTransaction).where(
            FinancialTransaction.type.in_([
                TransactionType.REVENUE,
                TransactionType.COMMISSION,
                TransactionType.ADJUSTMENT
            ])
        )
        
        # Apply filters
        conditions = []
        
        if filter_params.agency_id:
            conditions.append(FinancialTransaction.agency_id == UUID(filter_params.agency_id))
            
        if filter_params.model_ids:
            model_uuids = [UUID(mid) for mid in filter_params.model_ids]
            conditions.append(FinancialTransaction.model_id.in_(model_uuids))
            
        if filter_params.date_from:
            conditions.append(FinancialTransaction.transaction_date >= filter_params.date_from)
            
        if filter_params.date_to:
            conditions.append(FinancialTransaction.transaction_date <= filter_params.date_to)
            
        if filter_params.billing_cycle_id:
            conditions.append(
                FinancialTransaction.billing_cycle_id == UUID(filter_params.billing_cycle_id)
            )
            
        if conditions:
            query = query.where(and_(*conditions))
            
        result = await self.db.execute(query)
        transactions = result.scalars().all()
        
        # Process transactions
        model_data = {}
        total_gross = Decimal("0")
        total_commission = Decimal("0")
        total_net = Decimal("0")
        tier_counts = {}
        
        for txn in transactions:
            if txn.type == TransactionType.REVENUE:
                model_key = str(txn.model_id) if txn.model_id else "direct"
                
                if model_key not in model_data:
                    model_data[model_key] = {
                        "model_id": model_key,
                        "gross_revenue": Decimal("0"),
                        "commission_amount": Decimal("0"),
                        "net_revenue": Decimal("0"),
                        "transaction_count": 0
                    }
                    
                model_data[model_key]["gross_revenue"] += txn.amount
                model_data[model_key]["transaction_count"] += 1
                total_gross += txn.amount
                
                # Track commission tier
                if txn.metadata and "tier" in txn.metadata:
                    tier = txn.metadata["tier"]
                    tier_counts[tier] = tier_counts.get(tier, 0) + 1
                    
            elif txn.type == TransactionType.COMMISSION:
                model_key = str(txn.model_id) if txn.model_id else "direct"
                
                if model_key in model_data:
                    model_data[model_key]["commission_amount"] += txn.amount
                    
                total_commission += txn.amount
                
            elif txn.type == TransactionType.ADJUSTMENT and filter_params.include_adjustments:
                # Handle adjustments
                if txn.amount < 0:
                    total_commission += abs(txn.amount)
                else:
                    total_commission -= txn.amount
                    
        # Calculate net revenues
        for model_key, data in model_data.items():
            data["net_revenue"] = data["gross_revenue"] - data["commission_amount"]
            total_net += data["net_revenue"]
            
        # Build report
        return CommissionReport(
            period_start=filter_params.date_from,
            period_end=filter_params.date_to,
            total_gross_revenue=total_gross,
            total_commission=total_commission,
            total_net_revenue=total_net,
            model_breakdowns=list(model_data.values()),
            tier_distribution=tier_counts,
            generated_at=datetime.utcnow(),
            generated_by=str(generated_by_id)
        )
        
    async def create_commission_adjustment(
        self,
        adjustment_data: CommissionAdjustmentCreate,
        created_by_id: UUID
    ) -> FinancialTransaction:
        """
        Create a commission adjustment transaction.
        
        Used for corrections, bonuses, or penalties.
        """
        from ..domain.schemas import TransactionCreate
        
        transaction_data = TransactionCreate(
            agency_id=adjustment_data.agency_id,
            model_id=adjustment_data.model_id,
            type=TransactionType.ADJUSTMENT,
            amount=abs(adjustment_data.amount),
            currency=adjustment_data.currency,
            billing_cycle_id=adjustment_data.billing_cycle_id,
            description=f"Commission adjustment: {adjustment_data.reason}",
            metadata={
                "adjustment_type": "credit" if adjustment_data.amount > 0 else "debit",
                "original_amount": float(adjustment_data.amount),
                "reason": adjustment_data.reason
            }
        )
        
        adjustment = await self.transaction_service.create_transaction(
            transaction_data,
            created_by_id
        )
        
        logger.info(
            f"Commission adjustment created: {adjustment.id} "
            f"Amount: {adjustment_data.amount} Reason: {adjustment_data.reason}"
        )
        
        return adjustment
        
    async def _get_applicable_rule(
        self,
        agency_id: UUID,
        model_id: Optional[UUID],
        as_of_date: datetime
    ) -> Optional[CommissionRule]:
        """Get the applicable commission rule for a given date."""
        query = select(CommissionRule).where(
            and_(
                CommissionRule.agency_id == agency_id,
                CommissionRule.effective_from <= as_of_date,
                or_(
                    CommissionRule.effective_until.is_(None),
                    CommissionRule.effective_until >= as_of_date
                )
            )
        )
        
        # Prefer model-specific rules
        if model_id:
            query = query.where(
                or_(
                    CommissionRule.model_id == model_id,
                    CommissionRule.model_id.is_(None)
                )
            ).order_by(
                CommissionRule.model_id.desc(),  # Model-specific first
                desc(CommissionRule.is_override),  # Overrides first
                desc(CommissionRule.effective_from)
            )
        else:
            query = query.where(CommissionRule.model_id.is_(None)).order_by(
                desc(CommissionRule.is_override),
                desc(CommissionRule.effective_from)
            )
            
        query = query.limit(1)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
        
    async def _check_overlapping_rules(
        self,
        agency_id: str,
        model_id: Optional[str],
        effective_from: Optional[datetime],
        effective_until: Optional[datetime]
    ) -> bool:
        """Check if a rule would overlap with existing rules."""
        effective_from = effective_from or datetime.utcnow()
        
        query = select(func.count(CommissionRule.id)).where(
            and_(
                CommissionRule.agency_id == UUID(agency_id),
                CommissionRule.model_id == (UUID(model_id) if model_id else None),
                or_(
                    # New rule starts during existing rule
                    and_(
                        CommissionRule.effective_from <= effective_from,
                        or_(
                            CommissionRule.effective_until.is_(None),
                            CommissionRule.effective_until >= effective_from
                        )
                    ),
                    # New rule ends during existing rule
                    and_(
                        effective_until.is_not(None),
                        CommissionRule.effective_from <= effective_until,
                        or_(
                            CommissionRule.effective_until.is_(None),
                            CommissionRule.effective_until >= effective_until
                        )
                    ),
                    # New rule completely contains existing rule
                    and_(
                        effective_from <= CommissionRule.effective_from,
                        or_(
                            effective_until.is_(None),
                            and_(
                                CommissionRule.effective_until.is_not(None),
                                effective_until >= CommissionRule.effective_until
                            )
                        )
                    )
                )
            )
        )
        
        result = await self.db.execute(query)
        count = result.scalar() or 0
        
        return count > 0
        
    async def _end_existing_rules(
        self,
        agency_id: UUID,
        model_id: Optional[UUID],
        end_date: datetime
    ):
        """End existing rules before creating a new one."""
        query = select(CommissionRule).where(
            and_(
                CommissionRule.agency_id == agency_id,
                CommissionRule.model_id == model_id,
                or_(
                    CommissionRule.effective_until.is_(None),
                    CommissionRule.effective_until > end_date
                )
            )
        )
        
        result = await self.db.execute(query)
        rules = result.scalars().all()
        
        for rule in rules:
            rule.effective_until = end_date
            
        if rules:
            await self.db.commit()
            
    async def _emit_commission_event(
        self,
        rule: CommissionRule,
        action: str,
        user_id: UUID
    ):
        """Emit commission-related event."""
        if self.event_bus:
            event = Event(
                type=f"commission.{action}",
                data={
                    'rule_id': str(rule.id),
                    'agency_id': str(rule.agency_id),
                    'model_id': str(rule.model_id) if rule.model_id else None,
                    'tier': rule.tier,
                    'rate': float(rule.rate),
                    'is_override': rule.is_override,
                    'user_id': str(user_id)
                }
            )
            await self.event_bus.emit(event)
"""
Commission calculation and management service.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from models.financial import TransactionType
from modules.financial.domain.models import CommissionRule, CommissionTier, BillingCycle, FinancialTransaction
from modules.financial.domain.schemas import (
    CommissionRuleCreate,
    CommissionRuleUpdate,
    CommissionRuleResponse,
    CommissionOverrideRequest,
    CommissionCalculation,
    CommissionAdjustmentCreate,
    CommissionAdjustmentResponse,
    CommissionReport,
    CommissionReportFilter
)
from core.domain.models import Agency, ModelProfile, User


logger = logging.getLogger(__name__)


class CommissionService:
    """Handles commission calculation and rules management."""
    
    # Default commission rates by tier
    TIER_RATES = {
        CommissionTier.TIER_1: Decimal("70.0"),
        CommissionTier.TIER_2: Decimal("65.0"),
        CommissionTier.TIER_3: Decimal("60.0")
    }
    
    # Revenue thresholds for automatic tier upgrades
    TIER_THRESHOLDS = {
        CommissionTier.TIER_1: Decimal("0"),
        CommissionTier.TIER_2: Decimal("10000.00"),
        CommissionTier.TIER_3: Decimal("50000.00")
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_commission_rule(
        self,
        rule_data: CommissionRuleCreate,
        created_by: User
    ) -> CommissionRuleResponse:
        """
        Create a new commission rule.
        
        Args:
            rule_data: Commission rule details
            created_by: User creating the rule
            
        Returns:
            Created commission rule
        """
        # Verify agency exists
        agency = await self.db.get(Agency, rule_data.agency_id)
        if not agency:
            raise ValueError("Agency not found")
        
        # Verify model if specified
        if rule_data.model_id:
            model = await self.db.get(ModelProfile, rule_data.model_id)
            if not model or str(model.agency_id) != rule_data.agency_id:
                raise ValueError("Model not found or doesn't belong to agency")
        
        # Check for existing active rule
        existing = await self._get_active_rule(
            rule_data.agency_id,
            rule_data.model_id
        )
        
        if existing:
            # End the existing rule
            existing.effective_until = datetime.utcnow()
            self.db.add(existing)
        
        # Create new rule
        rule = CommissionRule(
            agency_id=rule_data.agency_id,
            model_id=rule_data.model_id,
            tier=rule_data.tier,
            rate=rule_data.rate,
            effective_from=rule_data.effective_from or datetime.utcnow(),
            effective_until=rule_data.effective_until
        )
        
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        
        return CommissionRuleResponse.model_validate(rule)
    
    async def update_commission_rule(
        self,
        rule_id: str,
        update_data: CommissionRuleUpdate,
        updated_by: User
    ) -> CommissionRuleResponse:
        """Update an existing commission rule."""
        rule = await self.db.get(CommissionRule, rule_id)
        if not rule:
            raise ValueError("Commission rule not found")
        
        # Update fields if provided
        if update_data.tier is not None:
            rule.tier = update_data.tier
        
        if update_data.rate is not None:
            rule.rate = update_data.rate
        
        if update_data.effective_until is not None:
            rule.effective_until = update_data.effective_until
        
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        
        return CommissionRuleResponse.model_validate(rule)
    
    async def override_commission(
        self,
        agency_id: str,
        model_id: Optional[str],
        override_data: CommissionOverrideRequest,
        super_admin: User
    ) -> CommissionRuleResponse:
        """
        Override commission for an agency or model (super_admin only).
        
        Args:
            agency_id: Agency ID
            model_id: Optional model ID for model-specific override
            override_data: Override details
            super_admin: Super admin user
            
        Returns:
            Created override rule
        """
        if super_admin.role != "super_admin":
            raise ValueError("Only super admins can override commission")
        
        # End existing rule
        existing = await self._get_active_rule(agency_id, model_id)
        if existing:
            existing.effective_until = datetime.utcnow()
            self.db.add(existing)
        
        # Create override rule
        rule = CommissionRule(
            agency_id=agency_id,
            model_id=model_id,
            tier=CommissionTier.CUSTOM,
            rate=override_data.rate,
            is_override=True,
            override_reason=override_data.reason,
            override_by=super_admin.id,
            override_at=datetime.utcnow(),
            effective_from=override_data.effective_from or datetime.utcnow(),
            effective_until=override_data.effective_until
        )
        
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        
        logger.info(
            f"Commission override created for agency {agency_id} "
            f"by {super_admin.username}: {override_data.rate}%"
        )
        
        return CommissionRuleResponse.model_validate(rule)
    
    async def calculate_commission(
        self,
        gross_amount: Decimal,
        model_id: str,
        calculation_date: Optional[datetime] = None
    ) -> CommissionCalculation:
        """
        Calculate commission for a given amount and model.
        
        Args:
            gross_amount: Gross revenue amount
            model_id: Model ID
            calculation_date: Date for calculation (defaults to now)
            
        Returns:
            Commission calculation details
        """
        if not calculation_date:
            calculation_date = datetime.utcnow()
        
        # Get model and agency
        model = await self.db.get(ModelProfile, model_id)
        if not model:
            raise ValueError("Model not found")
        
        # Get applicable commission rule
        rule = await self._get_applicable_rule(
            str(model.agency_id),
            model_id,
            calculation_date
        )
        
        if not rule:
            # Use default tier 1 if no rule exists
            commission_rate = self.TIER_RATES[CommissionTier.TIER_1]
            tier = CommissionTier.TIER_1
            is_override = False
        else:
            commission_rate = rule.rate
            tier = rule.tier
            is_override = rule.is_override
        
        # Calculate amounts
        commission_amount = gross_amount * (commission_rate / 100)
        net_amount = gross_amount - commission_amount
        
        return CommissionCalculation(
            gross_amount=gross_amount,
            commission_rate=commission_rate,
            commission_amount=commission_amount,
            net_amount=net_amount,
            tier=tier,
            is_override=is_override,
            calculation_date=calculation_date
        )
    
    async def get_commission_rules(
        self,
        agency_id: Optional[str] = None,
        model_id: Optional[str] = None,
        include_historical: bool = False
    ) -> List[CommissionRuleResponse]:
        """Get commission rules with optional filters."""
        query = select(CommissionRule)
        
        # Add filters
        conditions = []
        if agency_id:
            conditions.append(CommissionRule.agency_id == agency_id)
        if model_id:
            conditions.append(CommissionRule.model_id == model_id)
        
        if not include_historical:
            # Only active rules
            now = datetime.utcnow()
            conditions.append(
                or_(
                    CommissionRule.effective_until.is_(None),
                    CommissionRule.effective_until > now
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(CommissionRule.effective_from.desc())
        
        result = await self.db.execute(query)
        rules = result.scalars().all()
        
        return [CommissionRuleResponse.model_validate(rule) for rule in rules]
    
    async def process_billing_cycle_commission(
        self,
        billing_cycle_id: str
    ) -> Dict[str, Any]:
        """
        Process commission for an entire billing cycle.
        
        Args:
            billing_cycle_id: Billing cycle ID
            
        Returns:
            Commission summary
        """
        cycle = await self.db.get(BillingCycle, billing_cycle_id)
        if not cycle:
            raise ValueError("Billing cycle not found")
        
        if cycle.is_closed:
            raise ValueError("Billing cycle is already closed")
        
        # Get all revenue transactions for this cycle
        result = await self.db.execute(
            select(FinancialTransaction)
            .where(
                and_(
                    FinancialTransaction.billing_cycle_id == billing_cycle_id,
                    FinancialTransaction.type == TransactionType.REVENUE
                )
            )
        )
        transactions = result.scalars().all()
        
        # Calculate commission for each transaction
        total_gross = Decimal("0")
        total_commission = Decimal("0")
        commission_by_model = {}
        
        for tx in transactions:
            if tx.model_id:
                calc = await self.calculate_commission(
                    tx.amount,
                    str(tx.model_id),
                    tx.transaction_date
                )
                
                total_gross += calc.gross_amount
                total_commission += calc.commission_amount
                
                if str(tx.model_id) not in commission_by_model:
                    commission_by_model[str(tx.model_id)] = {
                        'gross': Decimal("0"),
                        'commission': Decimal("0"),
                        'net': Decimal("0")
                    }
                
                model_data = commission_by_model[str(tx.model_id)]
                model_data['gross'] += calc.gross_amount
                model_data['commission'] += calc.commission_amount
                model_data['net'] += calc.net_amount
        
        # Update billing cycle
        cycle.gross_revenue = total_gross
        cycle.total_commission = total_commission
        cycle.net_revenue = total_gross - total_commission
        
        self.db.add(cycle)
        await self.db.commit()
        
        return {
            'billing_cycle_id': billing_cycle_id,
            'total_gross': total_gross,
            'total_commission': total_commission,
            'total_net': total_gross - total_commission,
            'models': commission_by_model
        }
    
    async def _get_active_rule(
        self,
        agency_id: str,
        model_id: Optional[str]
    ) -> Optional[CommissionRule]:
        """Get currently active rule for agency/model."""
        now = datetime.utcnow()
        
        query = select(CommissionRule).where(
            and_(
                CommissionRule.agency_id == agency_id,
                CommissionRule.model_id == model_id,
                CommissionRule.effective_from <= now,
                or_(
                    CommissionRule.effective_until.is_(None),
                    CommissionRule.effective_until > now
                )
            )
        )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_applicable_rule(
        self,
        agency_id: str,
        model_id: str,
        date: datetime
    ) -> Optional[CommissionRule]:
        """Get applicable rule for a specific date."""
        # First try model-specific rule
        query = select(CommissionRule).where(
            and_(
                CommissionRule.agency_id == agency_id,
                CommissionRule.model_id == model_id,
                CommissionRule.effective_from <= date,
                or_(
                    CommissionRule.effective_until.is_(None),
                    CommissionRule.effective_until > date
                )
            )
        )
        
        result = await self.db.execute(query)
        rule = result.scalar_one_or_none()
        
        if rule:
            return rule
        
        # Fall back to agency-wide rule
        query = select(CommissionRule).where(
            and_(
                CommissionRule.agency_id == agency_id,
                CommissionRule.model_id.is_(None),
                CommissionRule.effective_from <= date,
                or_(
                    CommissionRule.effective_until.is_(None),
                    CommissionRule.effective_until > date
                )
            )
        )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def calculate_tiered_commission(
        self,
        gross_amount: Decimal,
        model_id: str,
        total_revenue: Optional[Decimal] = None
    ) -> CommissionCalculation:
        """
        Calculate commission with automatic tier upgrades based on revenue.
        
        Args:
            gross_amount: Current transaction amount
            model_id: Model ID
            total_revenue: Total revenue for the model (for tier calculation)
            
        Returns:
            Commission calculation with tier information
        """
        # Get model
        model = await self.db.get(ModelProfile, model_id)
        if not model:
            raise ValueError("Model not found")
        
        # If total revenue not provided, calculate it
        if total_revenue is None:
            result = await self.db.execute(
                select(func.sum(FinancialTransaction.amount))
                .where(
                    and_(
                        FinancialTransaction.model_id == model_id,
                        FinancialTransaction.type == TransactionType.REVENUE
                    )
                )
            )
            total_revenue = result.scalar() or Decimal("0")
        
        # Determine tier based on total revenue
        current_tier = CommissionTier.TIER_1
        for tier, threshold in sorted(
            self.TIER_THRESHOLDS.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            if total_revenue >= threshold:
                current_tier = tier
                break
        
        # Check for custom rule
        rule = await self._get_applicable_rule(
            str(model.agency_id),
            model_id,
            datetime.utcnow()
        )
        
        if rule and not rule.is_override:
            # If there's a non-override rule, use it but update tier if needed
            if rule.tier != current_tier:
                rule.tier = current_tier
                rule.rate = self.TIER_RATES.get(current_tier, rule.rate)
                self.db.add(rule)
                await self.db.commit()
        
        # Calculate using standard method
        return await self.calculate_commission(
            gross_amount,
            model_id,
            datetime.utcnow()
        )
    
    async def bulk_calculate_commission(
        self,
        billing_cycle_id: str
    ) -> List[CommissionCalculation]:
        """
        Calculate commission for all transactions in a billing cycle.
        
        Args:
            billing_cycle_id: Billing cycle ID
            
        Returns:
            List of commission calculations
        """
        # Get all revenue transactions for the cycle
        result = await self.db.execute(
            select(FinancialTransaction)
            .where(
                and_(
                    FinancialTransaction.billing_cycle_id == billing_cycle_id,
                    FinancialTransaction.type == TransactionType.REVENUE
                )
            )
            .order_by(FinancialTransaction.transaction_date)
        )
        transactions = result.scalars().all()
        
        # Group by model for efficient calculation
        transactions_by_model = {}
        for tx in transactions:
            if tx.model_id:
                model_id = str(tx.model_id)
                if model_id not in transactions_by_model:
                    transactions_by_model[model_id] = []
                transactions_by_model[model_id].append(tx)
        
        calculations = []
        
        # Calculate commission for each model's transactions
        for model_id, model_transactions in transactions_by_model.items():
            running_total = Decimal("0")
            
            for tx in model_transactions:
                # Calculate with running total for tier consideration
                calc = await self.calculate_tiered_commission(
                    tx.amount,
                    model_id,
                    running_total
                )
                
                # Store calculation reference in transaction
                tx.commission_rate = calc.commission_rate
                tx.commission_amount = calc.commission_amount
                self.db.add(tx)
                
                calculations.append(calc)
                running_total += tx.amount
        
        await self.db.commit()
        return calculations
    
    async def create_commission_adjustment(
        self,
        adjustment_data: CommissionAdjustmentCreate,
        created_by: User
    ) -> CommissionAdjustmentResponse:
        """
        Create a commission adjustment (credit or debit).
        
        Args:
            adjustment_data: Adjustment details
            created_by: User creating the adjustment
            
        Returns:
            Created adjustment
        """
        # Verify permissions
        if created_by.role not in ["super_admin", "agency_owner", "agency_admin"]:
            raise ValueError("Insufficient permissions to create adjustments")
        
        # Create adjustment transaction
        adjustment_tx = FinancialTransaction(
            agency_id=adjustment_data.agency_id,
            model_id=adjustment_data.model_id,
            type=TransactionType.ADJUSTMENT,
            amount=adjustment_data.amount,
            currency=adjustment_data.currency or "USD",
            description=f"Commission adjustment: {adjustment_data.reason}",
            transaction_date=datetime.utcnow(),
            created_by_id=created_by.id,
            metadata={
                "adjustment_type": "commission",
                "reason": adjustment_data.reason,
                "billing_cycle_id": str(adjustment_data.billing_cycle_id) if adjustment_data.billing_cycle_id else None
            }
        )
        
        self.db.add(adjustment_tx)
        await self.db.commit()
        await self.db.refresh(adjustment_tx)
        
        logger.info(
            f"Commission adjustment created by {created_by.username}: "
            f"{adjustment_data.amount} for model {adjustment_data.model_id}"
        )
        
        return CommissionAdjustmentResponse(
            id=adjustment_tx.id,
            agency_id=adjustment_tx.agency_id,
            model_id=adjustment_tx.model_id,
            amount=adjustment_tx.amount,
            currency=adjustment_tx.currency,
            reason=adjustment_data.reason,
            created_at=adjustment_tx.created_at,
            created_by=created_by.username
        )
    
    async def generate_commission_report(
        self,
        filter_params: CommissionReportFilter,
        requesting_user: User
    ) -> CommissionReport:
        """
        Generate a detailed commission report.
        
        Args:
            filter_params: Report filters
            requesting_user: User requesting the report
            
        Returns:
            Commission report with detailed breakdown
        """
        # Build base query
        query = select(
            FinancialTransaction.model_id,
            func.sum(FinancialTransaction.amount).label('gross_revenue'),
            func.sum(FinancialTransaction.commission_amount).label('total_commission'),
            func.count(FinancialTransaction.id).label('transaction_count'),
            func.avg(FinancialTransaction.commission_rate).label('avg_commission_rate')
        ).where(
            FinancialTransaction.type == TransactionType.REVENUE
        ).group_by(FinancialTransaction.model_id)
        
        # Apply filters
        conditions = []
        
        if filter_params.agency_id:
            conditions.append(FinancialTransaction.agency_id == filter_params.agency_id)
        
        if filter_params.model_ids:
            conditions.append(FinancialTransaction.model_id.in_(filter_params.model_ids))
        
        if filter_params.date_from:
            conditions.append(FinancialTransaction.transaction_date >= filter_params.date_from)
        
        if filter_params.date_to:
            conditions.append(FinancialTransaction.transaction_date <= filter_params.date_to)
        
        if filter_params.billing_cycle_id:
            conditions.append(FinancialTransaction.billing_cycle_id == filter_params.billing_cycle_id)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Execute query
        result = await self.db.execute(query)
        model_stats = result.all()
        
        # Build report
        total_gross = Decimal("0")
        total_commission = Decimal("0")
        total_net = Decimal("0")
        model_breakdowns = []
        
        for stat in model_stats:
            if stat.model_id and stat.gross_revenue:
                gross = stat.gross_revenue
                commission = stat.total_commission or Decimal("0")
                net = gross - commission
                
                total_gross += gross
                total_commission += commission
                total_net += net
                
                # Get model details
                model = await self.db.get(ModelProfile, stat.model_id)
                if model:
                    model_breakdowns.append({
                        'model_id': str(stat.model_id),
                        'model_name': model.display_name,
                        'gross_revenue': gross,
                        'commission_amount': commission,
                        'net_amount': net,
                        'transaction_count': stat.transaction_count,
                        'avg_commission_rate': float(stat.avg_commission_rate or 0)
                    })
        
        # Get tier distribution
        tier_query = select(
            CommissionRule.tier,
            func.count(CommissionRule.id).label('count')
        ).group_by(CommissionRule.tier)
        
        if filter_params.agency_id:
            tier_query = tier_query.where(CommissionRule.agency_id == filter_params.agency_id)
        
        tier_result = await self.db.execute(tier_query)
        tier_distribution = {
            str(tier): count 
            for tier, count in tier_result.all()
        }
        
        return CommissionReport(
            period_start=filter_params.date_from,
            period_end=filter_params.date_to,
            total_gross_revenue=total_gross,
            total_commission=total_commission,
            total_net_revenue=total_net,
            model_breakdowns=model_breakdowns,
            tier_distribution=tier_distribution,
            generated_at=datetime.utcnow(),
            generated_by=requesting_user.username
        )
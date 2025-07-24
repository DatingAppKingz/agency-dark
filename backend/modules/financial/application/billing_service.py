"""
Billing cycle management service.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from modules.financial.domain.models import (
    BillingCycle,
    FinancialTransaction,
    TransactionType
)
from modules.financial.domain.schemas import (
    BillingCycleSummary,
    BillingCycleDetails
)
from core.domain.models import Agency, User


logger = logging.getLogger(__name__)


class BillingService:
    """Manages billing cycles and financial periods."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_billing_cycle(
        self,
        agency_id: str,
        cycle_start: datetime,
        cycle_end: datetime
    ) -> BillingCycleSummary:
        """
        Create a new billing cycle.
        
        Args:
            agency_id: Agency ID
            cycle_start: Start of billing period
            cycle_end: End of billing period
            
        Returns:
            Created billing cycle
        """
        # Verify agency exists
        agency = await self.db.get(Agency, agency_id)
        if not agency:
            raise ValueError("Agency not found")
        
        # Check for overlapping cycles
        existing = await self.db.execute(
            select(BillingCycle).where(
                and_(
                    BillingCycle.agency_id == agency_id,
                    or_(
                        and_(
                            BillingCycle.cycle_start <= cycle_start,
                            BillingCycle.cycle_end >= cycle_start
                        ),
                        and_(
                            BillingCycle.cycle_start <= cycle_end,
                            BillingCycle.cycle_end >= cycle_end
                        )
                    )
                )
            )
        )
        
        if existing.scalar_one_or_none():
            raise ValueError("Billing cycle overlaps with existing cycle")
        
        # Create cycle
        cycle = BillingCycle(
            agency_id=agency_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end
        )
        
        self.db.add(cycle)
        await self.db.commit()
        await self.db.refresh(cycle)
        
        logger.info(f"Created billing cycle for agency {agency_id}: {cycle_start} - {cycle_end}")
        
        return BillingCycleSummary.model_validate(cycle)
    
    async def close_billing_cycle(
        self,
        cycle_id: str,
        closed_by: User
    ) -> BillingCycleDetails:
        """
        Close a billing cycle and calculate final amounts.
        
        Args:
            cycle_id: Billing cycle ID
            closed_by: User closing the cycle
            
        Returns:
            Closed billing cycle details
        """
        cycle = await self.db.get(BillingCycle, cycle_id)
        if not cycle:
            raise ValueError("Billing cycle not found")
        
        if cycle.is_closed:
            raise ValueError("Billing cycle is already closed")
        
        # Calculate revenue for the cycle
        revenue_result = await self.db.execute(
            select(func.sum(FinancialTransaction.amount))
            .where(
                and_(
                    FinancialTransaction.agency_id == cycle.agency_id,
                    FinancialTransaction.type == TransactionType.REVENUE,
                    FinancialTransaction.transaction_date >= cycle.cycle_start,
                    FinancialTransaction.transaction_date <= cycle.cycle_end
                )
            )
        )
        
        gross_revenue = revenue_result.scalar() or Decimal("0")
        
        # Process commission calculations
        from modules.financial.application.commission_service import CommissionService
        commission_service = CommissionService(self.db)
        
        commission_result = await commission_service.process_billing_cycle_commission(
            str(cycle.id)
        )
        
        # Update cycle
        cycle.gross_revenue = commission_result['total_gross']
        cycle.total_commission = commission_result['total_commission']
        cycle.net_revenue = commission_result['total_net']
        cycle.is_closed = True
        cycle.closed_at = datetime.utcnow()
        cycle.closed_by = closed_by.id
        
        await self.db.commit()
        await self.db.refresh(cycle)
        
        # Get model revenue breakdown
        model_revenues = []
        for model_id, data in commission_result['models'].items():
            model_revenues.append({
                'model_id': model_id,
                'gross_revenue': data['gross'],
                'commission': data['commission'],
                'net_revenue': data['net']
            })
        
        # Count pending payouts
        from modules.financial.domain.models import Payout, PayoutStatus
        payout_result = await self.db.execute(
            select(
                func.count(Payout.id).filter(Payout.status == PayoutStatus.PENDING),
                func.count(Payout.id).filter(Payout.status == PayoutStatus.COMPLETED),
                func.sum(Payout.amount)
            )
            .where(Payout.billing_cycle_id == cycle.id)
        )
        
        pending_count, completed_count, total_payout = payout_result.one()
        
        return BillingCycleDetails(
            id=str(cycle.id),
            agency_id=str(cycle.agency_id),
            cycle_start=cycle.cycle_start,
            cycle_end=cycle.cycle_end,
            gross_revenue=cycle.gross_revenue,
            total_commission=cycle.total_commission,
            net_revenue=cycle.net_revenue,
            is_closed=cycle.is_closed,
            closed_at=cycle.closed_at,
            model_revenues=model_revenues,
            pending_payouts=pending_count or 0,
            completed_payouts=completed_count or 0,
            total_payout_amount=total_payout or Decimal("0")
        )
    
    async def get_billing_cycles(
        self,
        agency_id: Optional[str] = None,
        include_open: bool = True,
        include_closed: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[BillingCycleSummary]:
        """Get billing cycles with optional filters."""
        query = select(BillingCycle)
        
        # Add filters
        conditions = []
        if agency_id:
            conditions.append(BillingCycle.agency_id == agency_id)
        
        if not include_open:
            conditions.append(BillingCycle.is_closed == True)
        elif not include_closed:
            conditions.append(BillingCycle.is_closed == False)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(BillingCycle.cycle_start.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        cycles = result.scalars().all()
        
        return [BillingCycleSummary.model_validate(cycle) for cycle in cycles]
    
    async def get_current_cycle(
        self,
        agency_id: str
    ) -> Optional[BillingCycleSummary]:
        """Get current open billing cycle for an agency."""
        now = datetime.utcnow()
        
        result = await self.db.execute(
            select(BillingCycle).where(
                and_(
                    BillingCycle.agency_id == agency_id,
                    BillingCycle.cycle_start <= now,
                    BillingCycle.cycle_end >= now,
                    BillingCycle.is_closed == False
                )
            )
        )
        
        cycle = result.scalar_one_or_none()
        
        if cycle:
            return BillingCycleSummary.model_validate(cycle)
        
        return None
    
    async def create_monthly_cycles(
        self,
        agency_id: str,
        start_date: date,
        months: int = 12
    ) -> List[BillingCycleSummary]:
        """
        Create monthly billing cycles for an agency.
        
        Args:
            agency_id: Agency ID
            start_date: Start date for first cycle
            months: Number of months to create
            
        Returns:
            Created billing cycles
        """
        created_cycles = []
        
        for i in range(months):
            # Calculate cycle dates
            cycle_start = datetime.combine(
                start_date + relativedelta(months=i),
                datetime.min.time()
            )
            
            # End of month
            next_month = cycle_start + relativedelta(months=1)
            cycle_end = datetime.combine(
                next_month - timedelta(days=1),
                datetime.max.time()
            )
            
            try:
                cycle = await self.create_billing_cycle(
                    agency_id,
                    cycle_start,
                    cycle_end
                )
                created_cycles.append(cycle)
            except ValueError as e:
                logger.warning(f"Skipping cycle {cycle_start} - {cycle_end}: {e}")
        
        return created_cycles
    
    async def process_auto_close(self):
        """Automatically close billing cycles that have ended."""
        # Get ended but not closed cycles
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        result = await self.db.execute(
            select(BillingCycle).where(
                and_(
                    BillingCycle.cycle_end < yesterday,
                    BillingCycle.is_closed == False
                )
            )
        )
        
        cycles = result.scalars().all()
        
        closed_count = 0
        
        # Get system user for auto-close
        system_user = await self.db.execute(
            select(User).where(User.username == "system")
        )
        system_user = system_user.scalar_one_or_none()
        
        if not system_user:
            logger.error("System user not found for auto-close")
            return closed_count
        
        for cycle in cycles:
            try:
                await self.close_billing_cycle(str(cycle.id), system_user)
                closed_count += 1
                
                # Create next cycle
                next_start = cycle.cycle_end + timedelta(seconds=1)
                next_end = next_start + relativedelta(months=1) - timedelta(seconds=1)
                
                await self.create_billing_cycle(
                    str(cycle.agency_id),
                    next_start,
                    next_end
                )
                
            except Exception as e:
                logger.error(f"Failed to auto-close cycle {cycle.id}: {e}")
        
        logger.info(f"Auto-closed {closed_count} billing cycles")
        
        return closed_count
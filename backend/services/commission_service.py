"""Commission calculation service with tiered structure."""

from decimal import Decimal
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from core.logger import get_logger
from models.financial import Transaction, TransactionStatus
from models.model import Model

logger = get_logger(__name__)


class CommissionService:
    """Service for calculating commissions with tiered structure."""
    
    # Tiered commission rates
    COMMISSION_TIERS = [
        # (threshold, rate)
        (Decimal("0"), Decimal("0.20")),      # 0-$10k: 20%
        (Decimal("10000"), Decimal("0.25")),   # $10k-$25k: 25%
        (Decimal("25000"), Decimal("0.30")),   # $25k-$50k: 30%
        (Decimal("50000"), Decimal("0.35")),   # $50k+: 35%
    ]
    
    # Platform fee (fixed)
    PLATFORM_FEE_RATE = Decimal("0.20")  # 20% platform fee
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_model_monthly_revenue(
        self, 
        model_id: int, 
        month: Optional[datetime] = None
    ) -> Decimal:
        """Get total revenue for a model in a specific month."""
        if not month:
            month = datetime.utcnow()
        
        # Calculate month boundaries
        month_start = month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month.month == 12:
            month_end = month_start.replace(year=month.year + 1, month=1) - timedelta(seconds=1)
        else:
            month_end = month_start.replace(month=month.month + 1) - timedelta(seconds=1)
        
        # Query total revenue for the month
        result = await self.db.scalar(
            select(func.coalesce(func.sum(Transaction.gross_amount), 0))
            .where(
                and_(
                    Transaction.model_id == model_id,
                    Transaction.status == TransactionStatus.COMPLETED,
                    Transaction.created_at >= month_start,
                    Transaction.created_at <= month_end
                )
            )
        )
        
        return Decimal(str(result))
    
    def calculate_agency_commission_rate(self, monthly_revenue: Decimal) -> Decimal:
        """Calculate agency commission rate based on monthly revenue tier."""
        for threshold, rate in reversed(self.COMMISSION_TIERS):
            if monthly_revenue >= threshold:
                return rate
        
        # Default to lowest tier
        return self.COMMISSION_TIERS[0][1]
    
    def calculate_tiered_commission(
        self, 
        gross_amount: Decimal, 
        monthly_revenue_before: Decimal
    ) -> Dict[str, Decimal]:
        """
        Calculate commission with tiered structure.
        
        Args:
            gross_amount: The transaction amount
            monthly_revenue_before: Model's revenue this month before this transaction
            
        Returns:
            Dict with platform_fee, agency_fee, and model_earnings
        """
        # Calculate platform fee (fixed rate)
        platform_fee = gross_amount * self.PLATFORM_FEE_RATE
        
        # Amount after platform fee
        after_platform = gross_amount - platform_fee
        
        # If transaction crosses tiers, calculate commission for each tier
        remaining_amount = after_platform
        total_agency_fee = Decimal("0")
        current_revenue = monthly_revenue_before
        
        for i, (threshold, rate) in enumerate(self.COMMISSION_TIERS):
            # Get next tier threshold (or None for last tier)
            next_threshold = self.COMMISSION_TIERS[i + 1][0] if i + 1 < len(self.COMMISSION_TIERS) else None
            
            if current_revenue >= threshold:
                # Calculate how much of this transaction falls in this tier
                if next_threshold and current_revenue < next_threshold:
                    # We're in this tier, calculate how much room until next tier
                    tier_room = next_threshold - current_revenue
                    tier_amount = min(remaining_amount, tier_room)
                else:
                    # We're in the highest tier or fully within a tier
                    if next_threshold is None or current_revenue >= next_threshold:
                        # In highest tier or above this tier
                        tier_amount = remaining_amount if not next_threshold else Decimal("0")
                    else:
                        tier_amount = remaining_amount
                
                if tier_amount > 0:
                    # Calculate commission for this portion
                    tier_fee = tier_amount * rate
                    total_agency_fee += tier_fee
                    remaining_amount -= tier_amount
                    current_revenue += tier_amount
                    
                    logger.debug(
                        f"Tier {threshold}: {tier_amount} @ {rate*100}% = {tier_fee}",
                        extra={
                            "tier_threshold": float(threshold),
                            "tier_rate": float(rate),
                            "tier_amount": float(tier_amount),
                            "tier_fee": float(tier_fee)
                        }
                    )
            
            if remaining_amount <= 0:
                break
        
        # Calculate model earnings
        model_earnings = after_platform - total_agency_fee
        
        logger.info(
            f"Commission calculated: gross={gross_amount}, platform={platform_fee}, "
            f"agency={total_agency_fee}, model={model_earnings}",
            extra={
                "gross_amount": float(gross_amount),
                "platform_fee": float(platform_fee),
                "agency_fee": float(total_agency_fee),
                "model_earnings": float(model_earnings),
                "monthly_revenue_before": float(monthly_revenue_before)
            }
        )
        
        return {
            "platform_fee": platform_fee,
            "agency_fee": total_agency_fee,
            "model_earnings": model_earnings
        }
    
    async def calculate_transaction_fees(
        self,
        model_id: int,
        gross_amount: Decimal,
        transaction_date: Optional[datetime] = None
    ) -> Dict[str, Decimal]:
        """
        Calculate fees for a transaction with proper tier handling.
        
        Args:
            model_id: The model ID
            gross_amount: The transaction amount
            transaction_date: Transaction date (defaults to now)
            
        Returns:
            Dict with platform_fee, agency_fee, and model_earnings
        """
        if not transaction_date:
            transaction_date = datetime.utcnow()
        
        # Get model's monthly revenue before this transaction
        monthly_revenue = await self.get_model_monthly_revenue(model_id, transaction_date)
        
        # Calculate fees with tiered structure
        return self.calculate_tiered_commission(gross_amount, monthly_revenue)
    
    def get_tier_info(self, monthly_revenue: Decimal) -> Dict[str, any]:
        """Get information about current tier and progress to next."""
        current_tier = None
        current_rate = None
        next_tier = None
        progress_to_next = None
        
        for i, (threshold, rate) in enumerate(self.COMMISSION_TIERS):
            if monthly_revenue >= threshold:
                current_tier = threshold
                current_rate = rate
                
                # Check if there's a next tier
                if i + 1 < len(self.COMMISSION_TIERS):
                    next_tier = self.COMMISSION_TIERS[i + 1][0]
                    progress_to_next = (monthly_revenue - threshold) / (next_tier - threshold)
        
        return {
            "current_tier": float(current_tier) if current_tier else 0,
            "current_rate": float(current_rate) if current_rate else 0.20,
            "next_tier": float(next_tier) if next_tier else None,
            "progress_to_next": float(progress_to_next) if progress_to_next else None,
            "monthly_revenue": float(monthly_revenue)
        }
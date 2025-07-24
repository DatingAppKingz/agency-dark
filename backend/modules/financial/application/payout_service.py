"""
Payout management service for models and agencies.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update

from modules.financial.domain.models import (
    Payout,
    PayoutStatus,
    BillingCycle,
    CryptoWallet,
    FinancialTransaction,
    TransactionType
)
from modules.financial.domain.schemas import (
    PayoutRequest,
    PayoutResponse,
    PayoutStatusUpdate
)
from core.domain.models import User, Agency, ModelProfile
from modules.financial.application.crypto_service import CryptoService


logger = logging.getLogger(__name__)


class PayoutService:
    """Manages payouts for models and agencies."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.crypto_service = CryptoService(db)
    
    async def create_payout(
        self,
        payout_data: PayoutRequest,
        created_by: User
    ) -> PayoutResponse:
        """
        Create a new payout request.
        
        Args:
            payout_data: Payout details
            created_by: User creating the payout
            
        Returns:
            Created payout
        """
        # Verify billing cycle exists and is closed
        cycle = await self.db.get(BillingCycle, payout_data.billing_cycle_id)
        if not cycle:
            raise ValueError("Billing cycle not found")
        
        if not cycle.is_closed:
            raise ValueError("Billing cycle must be closed before creating payouts")
        
        # Verify recipient
        recipient = await self.db.get(User, payout_data.recipient_id)
        if not recipient:
            raise ValueError("Recipient not found")
        
        # Verify recipient type matches
        if payout_data.recipient_type == "model":
            # Check if recipient has a model profile
            result = await self.db.execute(
                select(ModelProfile).where(
                    ModelProfile.user_id == payout_data.recipient_id
                )
            )
            if not result.scalar_one_or_none():
                raise ValueError("Recipient is not a model")
        elif payout_data.recipient_type == "agency":
            # Check if recipient is agency owner
            if recipient.role != "agency_owner":
                raise ValueError("Recipient is not an agency owner")
        
        # Validate payment details
        if payout_data.payment_method == "crypto":
            # Verify crypto wallet exists
            wallet_id = payout_data.payment_details.get('wallet_id')
            if not wallet_id:
                raise ValueError("Crypto wallet ID required")
            
            wallet = await self.db.get(CryptoWallet, wallet_id)
            if not wallet or str(wallet.user_id) != payout_data.recipient_id:
                raise ValueError("Invalid crypto wallet")
            
            if not wallet.is_active:
                raise ValueError("Crypto wallet is not active")
        
        # Check for duplicate payout
        existing = await self.db.execute(
            select(Payout).where(
                and_(
                    Payout.billing_cycle_id == payout_data.billing_cycle_id,
                    Payout.recipient_id == payout_data.recipient_id,
                    Payout.status != PayoutStatus.CANCELLED
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Payout already exists for this recipient in this cycle")
        
        # Create payout
        payout = Payout(
            billing_cycle_id=payout_data.billing_cycle_id,
            recipient_id=payout_data.recipient_id,
            recipient_type=payout_data.recipient_type,
            amount=payout_data.amount,
            payment_method=payout_data.payment_method,
            payment_details=payout_data.payment_details,
            scheduled_at=payout_data.scheduled_at or datetime.utcnow()
        )
        
        self.db.add(payout)
        
        # Create financial transaction
        transaction = FinancialTransaction(
            agency_id=cycle.agency_id,
            user_id=payout_data.recipient_id,
            type=TransactionType.PAYOUT,
            amount=payout_data.amount,
            billing_cycle_id=payout_data.billing_cycle_id,
            payout_id=payout.id,
            description=f"Payout for billing cycle {cycle.cycle_start.date()} - {cycle.cycle_end.date()}",
            transaction_date=datetime.utcnow()
        )
        
        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(payout)
        
        logger.info(f"Payout created: {payout.id} for {payout_data.amount}")
        
        return PayoutResponse.model_validate(payout)
    
    async def process_payout(
        self,
        payout_id: str
    ) -> PayoutResponse:
        """
        Process a pending payout.
        
        Args:
            payout_id: Payout ID
            
        Returns:
            Updated payout
        """
        payout = await self.db.get(Payout, payout_id)
        if not payout:
            raise ValueError("Payout not found")
        
        if payout.status != PayoutStatus.PENDING:
            raise ValueError(f"Cannot process payout in {payout.status} status")
        
        # Update status to processing
        payout.status = PayoutStatus.PROCESSING
        payout.processed_at = datetime.utcnow()
        await self.db.commit()
        
        try:
            if payout.payment_method == "crypto":
                # Process crypto payment
                result = await self.crypto_service.process_payout(payout)
                
                if result['success']:
                    payout.status = PayoutStatus.COMPLETED
                    payout.transaction_hash = result.get('transaction_hash')
                    payout.completed_at = datetime.utcnow()
                else:
                    payout.status = PayoutStatus.FAILED
                    payout.failure_reason = result.get('error')
                    payout.retry_count += 1
            else:
                # Bank transfer would be handled differently
                raise NotImplementedError("Bank transfer not implemented")
                
        except Exception as e:
            logger.error(f"Payout processing failed: {e}")
            payout.status = PayoutStatus.FAILED
            payout.failure_reason = str(e)
            payout.retry_count += 1
        
        await self.db.commit()
        await self.db.refresh(payout)
        
        return PayoutResponse.model_validate(payout)
    
    async def update_payout_status(
        self,
        payout_id: str,
        status_update: PayoutStatusUpdate
    ) -> PayoutResponse:
        """Update payout status (e.g., from webhook)."""
        payout = await self.db.get(Payout, payout_id)
        if not payout:
            raise ValueError("Payout not found")
        
        payout.status = status_update.status
        
        if status_update.transaction_id:
            payout.transaction_id = status_update.transaction_id
        
        if status_update.transaction_hash:
            payout.transaction_hash = status_update.transaction_hash
        
        if status_update.failure_reason:
            payout.failure_reason = status_update.failure_reason
        
        if status_update.status == PayoutStatus.COMPLETED:
            payout.completed_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(payout)
        
        logger.info(f"Payout {payout_id} status updated to {status_update.status}")
        
        return PayoutResponse.model_validate(payout)
    
    async def get_payouts(
        self,
        billing_cycle_id: Optional[str] = None,
        recipient_id: Optional[str] = None,
        status: Optional[PayoutStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[PayoutResponse]:
        """Get payouts with optional filters."""
        query = select(Payout)
        
        # Add filters
        conditions = []
        if billing_cycle_id:
            conditions.append(Payout.billing_cycle_id == billing_cycle_id)
        if recipient_id:
            conditions.append(Payout.recipient_id == recipient_id)
        if status:
            conditions.append(Payout.status == status)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(Payout.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        payouts = result.scalars().all()
        
        return [PayoutResponse.model_validate(payout) for payout in payouts]
    
    async def create_billing_cycle_payouts(
        self,
        billing_cycle_id: str,
        created_by: User
    ) -> List[PayoutResponse]:
        """
        Create payouts for all eligible recipients in a billing cycle.
        
        Args:
            billing_cycle_id: Billing cycle ID
            created_by: User creating payouts
            
        Returns:
            List of created payouts
        """
        cycle = await self.db.get(BillingCycle, billing_cycle_id)
        if not cycle:
            raise ValueError("Billing cycle not found")
        
        if not cycle.is_closed:
            raise ValueError("Billing cycle must be closed before creating payouts")
        
        # Get revenue by model for this cycle
        result = await self.db.execute(
            select(
                FinancialTransaction.user_id,
                func.sum(FinancialTransaction.amount).label('total')
            )
            .where(
                and_(
                    FinancialTransaction.billing_cycle_id == billing_cycle_id,
                    FinancialTransaction.type == TransactionType.REVENUE,
                    FinancialTransaction.user_id.isnot(None)
                )
            )
            .group_by(FinancialTransaction.user_id)
        )
        
        model_revenues = result.all()
        
        # Get commission service to calculate net amounts
        from modules.financial.application.commission_service import CommissionService
        commission_service = CommissionService(self.db)
        
        created_payouts = []
        
        for user_id, gross_amount in model_revenues:
            # Get model profile
            model_result = await self.db.execute(
                select(ModelProfile).where(ModelProfile.user_id == user_id)
            )
            model = model_result.scalar_one_or_none()
            
            if not model:
                continue
            
            # Calculate commission
            calc = await commission_service.calculate_commission(
                gross_amount,
                str(model.id),
                cycle.cycle_end
            )
            
            # Get default crypto wallet for model
            wallet_result = await self.db.execute(
                select(CryptoWallet).where(
                    and_(
                        CryptoWallet.user_id == user_id,
                        CryptoWallet.is_default == True,
                        CryptoWallet.is_active == True
                    )
                )
            )
            wallet = wallet_result.scalar_one_or_none()
            
            if not wallet:
                logger.warning(f"No default wallet for model {model.id}, skipping payout")
                continue
            
            # Create payout for net amount
            payout_data = PayoutRequest(
                billing_cycle_id=billing_cycle_id,
                recipient_id=str(user_id),
                recipient_type="model",
                amount=calc.net_amount,
                payment_method="crypto",
                payment_details={'wallet_id': str(wallet.id)},
                scheduled_at=datetime.utcnow() + timedelta(days=3)  # Schedule 3 days out
            )
            
            try:
                payout = await self.create_payout(payout_data, created_by)
                created_payouts.append(payout)
            except Exception as e:
                logger.error(f"Failed to create payout for model {model.id}: {e}")
        
        # Create agency payout for total commission
        if cycle.total_commission > 0:
            # Get agency owner
            agency = await self.db.get(Agency, cycle.agency_id)
            if agency:
                owner_result = await self.db.execute(
                    select(User).where(
                        and_(
                            User.agency_id == cycle.agency_id,
                            User.role == "agency_owner"
                        )
                    )
                )
                owner = owner_result.scalar_one_or_none()
                
                if owner:
                    # Get agency owner's wallet
                    wallet_result = await self.db.execute(
                        select(CryptoWallet).where(
                            and_(
                                CryptoWallet.user_id == owner.id,
                                CryptoWallet.is_default == True,
                                CryptoWallet.is_active == True
                            )
                        )
                    )
                    wallet = wallet_result.scalar_one_or_none()
                    
                    if wallet:
                        agency_payout_data = PayoutRequest(
                            billing_cycle_id=billing_cycle_id,
                            recipient_id=str(owner.id),
                            recipient_type="agency",
                            amount=cycle.total_commission,
                            payment_method="crypto",
                            payment_details={'wallet_id': str(wallet.id)},
                            scheduled_at=datetime.utcnow() + timedelta(days=3)
                        )
                        
                        try:
                            payout = await self.create_payout(agency_payout_data, created_by)
                            created_payouts.append(payout)
                        except Exception as e:
                            logger.error(f"Failed to create agency payout: {e}")
        
        return created_payouts
    
    async def process_scheduled_payouts(self):
        """Process all scheduled payouts that are due."""
        # Get pending payouts that are scheduled for now or earlier
        result = await self.db.execute(
            select(Payout).where(
                and_(
                    Payout.status == PayoutStatus.PENDING,
                    Payout.scheduled_at <= datetime.utcnow()
                )
            )
        )
        
        payouts = result.scalars().all()
        
        processed = 0
        failed = 0
        
        for payout in payouts:
            try:
                await self.process_payout(str(payout.id))
                processed += 1
            except Exception as e:
                logger.error(f"Failed to process payout {payout.id}: {e}")
                failed += 1
        
        logger.info(f"Processed {processed} payouts, {failed} failed")
        
        return {'processed': processed, 'failed': failed}
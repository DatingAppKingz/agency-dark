"""
Transaction recording and management service.
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload

from modules.financial.domain.models import (
    FinancialTransaction,
    TransactionType,
    BillingCycle,
    Payout,
    Invoice
)
from modules.financial.domain.schemas import (
    TransactionCreate,
    TransactionUpdate,
    TransactionResponse,
    TransactionFilter,
    TransactionSummary
)
from core.domain.models import User, Agency, ModelProfile
from core.exceptions import ValidationError, NotFoundError, BusinessLogicError


logger = logging.getLogger(__name__)


class TransactionService:
    """Manages financial transaction recording and querying."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_transaction(
        self,
        transaction_data: TransactionCreate,
        created_by: User
    ) -> TransactionResponse:
        """
        Create a new financial transaction with validation.
        
        Args:
            transaction_data: Transaction details
            created_by: User creating the transaction
            
        Returns:
            Created transaction
            
        Raises:
            ValidationError: If transaction data is invalid
            BusinessLogicError: If business rules are violated
        """
        # Validate transaction data
        await self._validate_transaction_data(transaction_data)
        
        # Get current balance if tracking is required
        balance_before = None
        balance_after = None
        
        if transaction_data.track_balance:
            balance_before = await self._get_current_balance(
                agency_id=transaction_data.agency_id,
                model_id=transaction_data.model_id,
                user_id=transaction_data.user_id
            )
            
            # Calculate new balance
            if transaction_data.type in [TransactionType.REVENUE, TransactionType.REFUND]:
                balance_after = balance_before + transaction_data.amount
            else:  # COMMISSION, PAYOUT, ADJUSTMENT
                balance_after = balance_before - transaction_data.amount
        
        # Create transaction
        transaction = FinancialTransaction(
            agency_id=transaction_data.agency_id,
            model_id=transaction_data.model_id,
            user_id=transaction_data.user_id,
            type=transaction_data.type,
            amount=transaction_data.amount,
            currency=transaction_data.currency or 'USD',
            billing_cycle_id=transaction_data.billing_cycle_id,
            payout_id=transaction_data.payout_id,
            invoice_id=transaction_data.invoice_id,
            external_reference=transaction_data.external_reference,
            description=transaction_data.description,
            balance_before=balance_before,
            balance_after=balance_after,
            transaction_date=transaction_data.transaction_date or datetime.utcnow()
        )
        
        self.db.add(transaction)
        
        try:
            await self.db.commit()
            await self.db.refresh(transaction)
            
            logger.info(
                f"Transaction created: {transaction.id} - "
                f"Type: {transaction.type}, Amount: {transaction.amount}"
            )
            
            return TransactionResponse.from_orm(transaction)
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create transaction: {str(e)}")
            raise BusinessLogicError(f"Failed to create transaction: {str(e)}")
    
    async def get_transaction(
        self,
        transaction_id: UUID,
        user: User
    ) -> TransactionResponse:
        """
        Get a transaction by ID with permission check.
        
        Args:
            transaction_id: Transaction ID
            user: User requesting the transaction
            
        Returns:
            Transaction details
            
        Raises:
            NotFoundError: If transaction not found
            ValidationError: If user lacks permission
        """
        query = select(FinancialTransaction).where(
            FinancialTransaction.id == transaction_id
        )
        
        # Apply tenant filter for non-super admins
        if user.role != "super_admin":
            query = query.where(FinancialTransaction.agency_id == user.agency_id)
        
        result = await self.db.execute(query)
        transaction = result.scalar_one_or_none()
        
        if not transaction:
            raise NotFoundError(f"Transaction {transaction_id} not found")
        
        return TransactionResponse.from_orm(transaction)
    
    async def list_transactions(
        self,
        filter_params: TransactionFilter,
        user: User,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[TransactionResponse], int]:
        """
        List transactions with filtering, pagination, and permissions.
        
        Args:
            filter_params: Filter parameters
            user: User requesting transactions
            page: Page number (1-based)
            page_size: Items per page
            
        Returns:
            Tuple of (transactions, total_count)
        """
        query = select(FinancialTransaction)
        
        # Apply filters
        conditions = []
        
        # Tenant filter for non-super admins
        if user.role != "super_admin":
            conditions.append(FinancialTransaction.agency_id == user.agency_id)
        elif filter_params.agency_id:
            conditions.append(FinancialTransaction.agency_id == filter_params.agency_id)
        
        if filter_params.model_id:
            conditions.append(FinancialTransaction.model_id == filter_params.model_id)
        
        if filter_params.user_id:
            conditions.append(FinancialTransaction.user_id == filter_params.user_id)
        
        if filter_params.type:
            conditions.append(FinancialTransaction.type == filter_params.type)
        
        if filter_params.billing_cycle_id:
            conditions.append(FinancialTransaction.billing_cycle_id == filter_params.billing_cycle_id)
        
        if filter_params.payout_id:
            conditions.append(FinancialTransaction.payout_id == filter_params.payout_id)
        
        if filter_params.date_from:
            conditions.append(FinancialTransaction.transaction_date >= filter_params.date_from)
        
        if filter_params.date_to:
            conditions.append(FinancialTransaction.transaction_date <= filter_params.date_to)
        
        if filter_params.amount_min:
            conditions.append(FinancialTransaction.amount >= filter_params.amount_min)
        
        if filter_params.amount_max:
            conditions.append(FinancialTransaction.amount <= filter_params.amount_max)
        
        if filter_params.search:
            search_pattern = f"%{filter_params.search}%"
            conditions.append(
                or_(
                    FinancialTransaction.description.ilike(search_pattern),
                    FinancialTransaction.external_reference.ilike(search_pattern)
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total_count = total_result.scalar() or 0
        
        # Apply sorting
        if filter_params.sort_by == "date":
            query = query.order_by(
                desc(FinancialTransaction.transaction_date) if filter_params.sort_desc 
                else FinancialTransaction.transaction_date
            )
        elif filter_params.sort_by == "amount":
            query = query.order_by(
                desc(FinancialTransaction.amount) if filter_params.sort_desc 
                else FinancialTransaction.amount
            )
        else:
            query = query.order_by(desc(FinancialTransaction.created_at))
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # Execute query
        result = await self.db.execute(query)
        transactions = result.scalars().all()
        
        return (
            [TransactionResponse.from_orm(t) for t in transactions],
            total_count
        )
    
    async def get_transaction_summary(
        self,
        filter_params: TransactionFilter,
        user: User
    ) -> TransactionSummary:
        """
        Get summary statistics for transactions.
        
        Args:
            filter_params: Filter parameters
            user: User requesting summary
            
        Returns:
            Transaction summary with totals and counts
        """
        # Base query with filters applied
        query = select(FinancialTransaction)
        conditions = []
        
        # Apply same filters as list_transactions
        if user.role != "super_admin":
            conditions.append(FinancialTransaction.agency_id == user.agency_id)
        elif filter_params.agency_id:
            conditions.append(FinancialTransaction.agency_id == filter_params.agency_id)
        
        if filter_params.model_id:
            conditions.append(FinancialTransaction.model_id == filter_params.model_id)
        
        if filter_params.date_from:
            conditions.append(FinancialTransaction.transaction_date >= filter_params.date_from)
        
        if filter_params.date_to:
            conditions.append(FinancialTransaction.transaction_date <= filter_params.date_to)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Get summary by transaction type
        summary_query = select(
            FinancialTransaction.type,
            func.count(FinancialTransaction.id).label('count'),
            func.sum(FinancialTransaction.amount).label('total')
        ).select_from(query.subquery()).group_by(FinancialTransaction.type)
        
        result = await self.db.execute(summary_query)
        summaries = result.all()
        
        # Build summary response
        summary_data = {
            "total_count": 0,
            "total_amount": Decimal("0.00"),
            "by_type": {}
        }
        
        for type_summary in summaries:
            summary_data["by_type"][type_summary.type] = {
                "count": type_summary.count,
                "total": float(type_summary.total or 0)
            }
            summary_data["total_count"] += type_summary.count
            summary_data["total_amount"] += type_summary.total or Decimal("0.00")
        
        # Calculate net flow
        revenue = summary_data["by_type"].get(TransactionType.REVENUE, {}).get("total", 0)
        refunds = summary_data["by_type"].get(TransactionType.REFUND, {}).get("total", 0)
        commissions = summary_data["by_type"].get(TransactionType.COMMISSION, {}).get("total", 0)
        payouts = summary_data["by_type"].get(TransactionType.PAYOUT, {}).get("total", 0)
        adjustments = summary_data["by_type"].get(TransactionType.ADJUSTMENT, {}).get("total", 0)
        
        summary_data["net_revenue"] = revenue - refunds
        summary_data["net_payout"] = payouts + commissions
        summary_data["net_balance"] = revenue + refunds - commissions - payouts + adjustments
        
        return TransactionSummary(**summary_data)
    
    async def update_transaction_status(
        self,
        transaction_id: UUID,
        status: str,
        updated_by: User,
        notes: Optional[str] = None
    ) -> TransactionResponse:
        """
        Update transaction status (for linked records).
        
        Args:
            transaction_id: Transaction ID
            status: New status
            updated_by: User updating the transaction
            notes: Optional notes
            
        Returns:
            Updated transaction
        """
        transaction = await self.get_transaction(transaction_id, updated_by)
        
        # For now, just add notes if provided
        if notes:
            current_desc = transaction.description or ""
            transaction.description = f"{current_desc}\n[{datetime.utcnow().isoformat()}] {notes}"
        
        await self.db.commit()
        await self.db.refresh(transaction)
        
        return TransactionResponse.from_orm(transaction)
    
    async def _validate_transaction_data(self, data: TransactionCreate) -> None:
        """Validate transaction data against business rules."""
        # Ensure amount is positive
        if data.amount <= 0:
            raise ValidationError("Transaction amount must be positive")
        
        # Validate entity relationships
        if data.agency_id:
            agency = await self.db.get(Agency, data.agency_id)
            if not agency:
                raise ValidationError(f"Agency {data.agency_id} not found")
        
        if data.model_id:
            model = await self.db.get(ModelProfile, data.model_id)
            if not model:
                raise ValidationError(f"Model {data.model_id} not found")
            
            # Ensure model belongs to agency
            if data.agency_id and model.agency_id != data.agency_id:
                raise ValidationError("Model does not belong to specified agency")
        
        if data.billing_cycle_id:
            cycle = await self.db.get(BillingCycle, data.billing_cycle_id)
            if not cycle:
                raise ValidationError(f"Billing cycle {data.billing_cycle_id} not found")
        
        # Validate transaction type rules
        if data.type == TransactionType.COMMISSION and not data.model_id:
            raise ValidationError("Commission transactions require a model_id")
        
        if data.type == TransactionType.PAYOUT and not data.payout_id:
            raise ValidationError("Payout transactions require a payout_id")
    
    async def _get_current_balance(
        self,
        agency_id: Optional[UUID] = None,
        model_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None
    ) -> Decimal:
        """Get current balance for an entity."""
        # Get the latest transaction with balance tracking
        query = select(FinancialTransaction).where(
            FinancialTransaction.balance_after.is_not(None)
        )
        
        if agency_id:
            query = query.where(FinancialTransaction.agency_id == agency_id)
        if model_id:
            query = query.where(FinancialTransaction.model_id == model_id)
        if user_id:
            query = query.where(FinancialTransaction.user_id == user_id)
        
        query = query.order_by(desc(FinancialTransaction.transaction_date)).limit(1)
        
        result = await self.db.execute(query)
        last_transaction = result.scalar_one_or_none()
        
        return last_transaction.balance_after if last_transaction else Decimal("0.00")
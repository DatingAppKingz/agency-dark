"""
Financial transaction API endpoints.
"""
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_current_user
from core.domain.models import User
from modules.financial.application.transaction_service import TransactionService
from modules.financial.domain.schemas import (
    TransactionCreate,
    TransactionUpdate,
    TransactionResponse,
    TransactionFilter,
    TransactionSummary
)


router = APIRouter(prefix="/transactions", tags=["financial-transactions"])


@router.post("/", response_model=TransactionResponse)
async def create_transaction(
    transaction_data: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new financial transaction.
    
    Required permissions:
    - SUPER_ADMIN: Can create any transaction
    - AGENCY_OWNER/ADMIN: Can create transactions for their agency
    - Others: Forbidden
    """
    # Permission check
    if current_user.role not in ["super_admin", "agency_owner", "agency_admin"]:
        raise ForbiddenException("Insufficient permissions to create transactions")
    
    # Ensure agency context for non-super admins
    if current_user.role != "super_admin" and not transaction_data.agency_id:
        transaction_data.agency_id = str(current_user.agency_id)
    
    service = TransactionService(db)
    return await service.create_transaction(transaction_data, current_user)


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: UUID = Path(..., description="Transaction ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a transaction by ID.
    
    Permissions:
    - Users can only view transactions from their own agency
    - SUPER_ADMIN can view any transaction
    """
    service = TransactionService(db)
    return await service.get_transaction(transaction_id, current_user)


@router.get("/", response_model=List[TransactionResponse])
async def list_transactions(
    # Filter parameters
    type: Optional[str] = Query(None, description="Transaction type"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    amount_min: Optional[float] = Query(None, description="Minimum amount"),
    amount_max: Optional[float] = Query(None, description="Maximum amount"),
    model_id: Optional[UUID] = Query(None, description="Model ID"),
    billing_cycle_id: Optional[UUID] = Query(None, description="Billing cycle ID"),
    payout_id: Optional[UUID] = Query(None, description="Payout ID"),
    search: Optional[str] = Query(None, description="Search in description/reference"),
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    # Sorting
    sort_by: Optional[str] = Query("date", description="Sort field: date, amount"),
    sort_desc: bool = Query(True, description="Sort descending"),
    # Dependencies
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List transactions with filtering and pagination.
    
    Permissions:
    - Users can only view transactions from their own agency
    - SUPER_ADMIN can filter by any agency
    """
    # Build filter
    filter_params = TransactionFilter(
        type=type,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        model_id=str(model_id) if model_id else None,
        billing_cycle_id=str(billing_cycle_id) if billing_cycle_id else None,
        payout_id=str(payout_id) if payout_id else None,
        search=search,
        sort_by=sort_by,
        sort_desc=sort_desc
    )
    
    service = TransactionService(db)
    transactions, total = await service.list_transactions(
        filter_params, current_user, page, page_size
    )
    
    # Add pagination headers
    return transactions


@router.get("/summary/stats", response_model=TransactionSummary)
async def get_transaction_summary(
    # Filter parameters (same as list)
    type: Optional[str] = Query(None, description="Transaction type"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    model_id: Optional[UUID] = Query(None, description="Model ID"),
    # Dependencies
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get transaction summary statistics.
    
    Returns aggregated data including:
    - Total counts and amounts by type
    - Net revenue and payout calculations
    - Balance summary
    """
    filter_params = TransactionFilter(
        type=type,
        date_from=date_from,
        date_to=date_to,
        model_id=str(model_id) if model_id else None
    )
    
    service = TransactionService(db)
    return await service.get_transaction_summary(filter_params, current_user)


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: UUID = Path(..., description="Transaction ID"),
    update_data: TransactionUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update transaction details (limited fields).
    
    Only allows updating:
    - description
    - external_reference
    
    Requires AGENCY_ADMIN or higher permissions.
    """
    if current_user.role not in ["super_admin", "agency_owner", "agency_admin"]:
        raise ForbiddenException("Insufficient permissions to update transactions")
    
    service = TransactionService(db)
    
    # Get transaction first to verify permissions
    transaction = await service.get_transaction(transaction_id, current_user)
    
    # Update only allowed fields
    if update_data.description is not None:
        notes = f"Updated by {current_user.email}: {update_data.description}"
    else:
        notes = None
    
    return await service.update_transaction_status(
        transaction_id,
        status="updated",
        updated_by=current_user,
        notes=notes
    )


@router.post("/bulk/import")
async def bulk_import_transactions(
    transactions: List[TransactionCreate] = Body(..., description="List of transactions to import"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk import transactions.
    
    Requires SUPER_ADMIN or AGENCY_OWNER permissions.
    Maximum 100 transactions per request.
    """
    if current_user.role not in ["super_admin", "agency_owner"]:
        raise ForbiddenException("Insufficient permissions for bulk import")
    
    if len(transactions) > 100:
        raise ValidationError("Maximum 100 transactions per bulk import")
    
    service = TransactionService(db)
    results = []
    errors = []
    
    for idx, transaction_data in enumerate(transactions):
        try:
            # Ensure agency context
            if current_user.role != "super_admin" and not transaction_data.agency_id:
                transaction_data.agency_id = str(current_user.agency_id)
            
            result = await service.create_transaction(transaction_data, current_user)
            results.append(result)
        except Exception as e:
            errors.append({
                "index": idx,
                "error": str(e),
                "data": transaction_data.dict()
            })
    
    return {
        "success_count": len(results),
        "error_count": len(errors),
        "errors": errors
    }


# Import necessary exceptions
from core.exceptions import ForbiddenException, ValidationError
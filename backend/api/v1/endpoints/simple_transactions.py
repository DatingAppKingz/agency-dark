"""Simple transaction endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal

from core.database import get_db
from models.financial import Transaction, TransactionType, TransactionStatus
from models.user import User
from models.model import Model
from api.v1.endpoints.auth_simple import get_current_user


router = APIRouter()


class TransactionCreate(BaseModel):
    model_id: int
    type: str  # Will convert to enum
    gross_amount: float
    net_amount: float
    currency: str = "USD"
    status: str = "COMPLETED"
    description: Optional[str] = None


class TransactionResponse(BaseModel):
    id: int
    model_id: int
    type: str
    status: str
    gross_amount: float
    net_amount: float
    currency: str
    description: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class TransactionStats(BaseModel):
    total_gross: float
    total_net: float
    transaction_count: int
    average_transaction: float


@router.post("/", response_model=TransactionResponse)
async def create_transaction(
    transaction: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new transaction."""
    # Verify model exists
    stmt = select(Model).where(Model.id == transaction.model_id)
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Convert string to enum
    try:
        trans_type = TransactionType[transaction.type.upper()]
        trans_status = TransactionStatus[transaction.status.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid transaction type or status")
    
    # Calculate fees
    platform_fee = Decimal(str(transaction.gross_amount - transaction.net_amount))
    
    new_transaction = Transaction(
        model_id=transaction.model_id,
        user_id=current_user.id,
        fan_id=1,  # Dummy fan ID for now
        type=trans_type,
        status=trans_status,
        gross_amount=Decimal(str(transaction.gross_amount)),
        platform_fee=platform_fee,
        net_amount=Decimal(str(transaction.net_amount)),
        currency=transaction.currency,
        description=transaction.description
    )
    
    db.add(new_transaction)
    await db.commit()
    await db.refresh(new_transaction)
    
    return new_transaction


@router.get("/", response_model=List[TransactionResponse])
async def list_transactions(
    skip: int = 0,
    limit: int = 100,
    model_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of transactions."""
    stmt = select(Transaction)
    
    if model_id:
        stmt = stmt.where(Transaction.model_id == model_id)
    
    stmt = stmt.offset(skip).limit(limit).order_by(Transaction.created_at.desc())
    
    result = await db.execute(stmt)
    transactions = result.scalars().all()
    return transactions


@router.get("/stats/model/{model_id}", response_model=TransactionStats)
async def get_transaction_stats(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get transaction statistics for a model."""
    # Calculate stats
    stmt = select(
        func.sum(Transaction.gross_amount).label('total_gross'),
        func.sum(Transaction.net_amount).label('total_net'),
        func.count(Transaction.id).label('count')
    ).where(
        Transaction.model_id == model_id,
        Transaction.status == TransactionStatus.COMPLETED
    )
    
    result = await db.execute(stmt)
    stats = result.first()
    
    total_gross = float(stats.total_gross or 0)
    total_net = float(stats.total_net or 0)
    count = stats.count or 0
    
    return TransactionStats(
        total_gross=total_gross,
        total_net=total_net,
        transaction_count=count,
        average_transaction=total_gross / count if count > 0 else 0
    )
"""
Simplified financial management endpoints.
"""
from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from core.dependencies import CurrentUser

router = APIRouter(tags=["financial"])


class InvoiceListResponse(BaseModel):
    invoices: List[dict] = []
    total: int = 0


class PayoutListResponse(BaseModel):
    payouts: List[dict] = []
    total: int = 0


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    List invoices (returns empty list for now).
    """
    return InvoiceListResponse(
        invoices=[],
        total=0
    )


@router.get("/payouts", response_model=PayoutListResponse)
async def list_payouts(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    List payouts (returns empty list for now).
    """
    return PayoutListResponse(
        payouts=[],
        total=0
    )
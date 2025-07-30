"""Financial background tasks."""

from datetime import datetime, timedelta
from decimal import Decimal
import asyncio

from celery import Task
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.celery_app import celery_app
from core.database import AsyncSessionLocal
from core.redis import redis_manager
from models.model import Model
from models.financial import Payout, PayoutStatus, Transaction, TransactionStatus
from models.subscriber import Subscriber, SubscriptionStatus
from models.user import User


@celery_app.task
def process_pending_payouts():
    """Process all pending payouts."""
    async def _process():
        async with AsyncSessionLocal() as db:
            # Get pending payouts
            stmt = select(Payout).where(Payout.status == PayoutStatus.PENDING)
            result = await db.execute(stmt)
            payouts = result.scalars().all()
            
            processed = 0
            failed = 0
            
            for payout in payouts:
                try:
                    # Here you would integrate with actual payment processor
                    # For now, we'll simulate processing
                    
                    # Mark as processing
                    payout.status = PayoutStatus.PROCESSING
                    await db.commit()
                    
                    # Simulate payment processing
                    await asyncio.sleep(1)
                    
                    # Mark as completed
                    payout.status = PayoutStatus.COMPLETED
                    payout.processed_date = datetime.utcnow().isoformat()
                    payout.completed_date = datetime.utcnow().isoformat()
                    payout.transaction_reference = f"TX-{payout.id}-{datetime.utcnow().timestamp()}"
                    
                    await db.commit()
                    processed += 1
                    
                except Exception as e:
                    # Mark as failed
                    payout.status = PayoutStatus.FAILED
                    payout.notes = f"Processing failed: {str(e)}"
                    await db.commit()
                    failed += 1
            
            return {
                "total": len(payouts),
                "processed": processed,
                "failed": failed,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_process())
    finally:
        loop.close()


@celery_app.task
def check_subscription_expirations():
    """Check for expiring subscriptions and process renewals."""
    async def _check():
        async with AsyncSessionLocal() as db:
            # Get subscriptions expiring in next 24 hours
            tomorrow = datetime.utcnow() + timedelta(days=1)
            
            stmt = select(Subscriber).where(
                and_(
                    Subscriber.status == SubscriptionStatus.ACTIVE,
                    Subscriber.expires_at <= tomorrow.isoformat(),
                    Subscriber.auto_renew == True
                )
            )
            
            result = await db.execute(stmt)
            expiring_subs = result.scalars().all()
            
            renewed = 0
            expired = 0
            
            for sub in expiring_subs:
                if sub.auto_renew:
                    # Process renewal
                    # Here you would charge the subscription fee
                    
                    # Create renewal transaction
                    transaction = Transaction(
                        model_id=sub.model_id,
                        user_id=sub.user_id,
                        type=TransactionType.SUBSCRIPTION_RENEWAL,
                        status=TransactionStatus.COMPLETED,
                        gross_amount=sub.subscription_price,
                        platform_fee=sub.subscription_price * Decimal("0.20"),
                        agency_fee=sub.subscription_price * Decimal("0.10"),
                        model_earnings=sub.subscription_price * Decimal("0.70"),
                        description="Monthly subscription renewal",
                        completed_at=datetime.utcnow()
                    )
                    db.add(transaction)
                    
                    # Extend subscription
                    sub.expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat()
                    renewed += 1
                else:
                    # Mark as expired
                    sub.status = SubscriptionStatus.EXPIRED
                    sub.is_active = False
                    expired += 1
            
            await db.commit()
            
            return {
                "checked": len(expiring_subs),
                "renewed": renewed,
                "expired": expired,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_check())
    finally:
        loop.close()


@celery_app.task
def reconcile_platform_transactions(platform: str, start_date: str, end_date: str):
    """Reconcile transactions with platform data."""
    # This would connect to platform APIs and reconcile transactions
    return {
        "platform": platform,
        "period": f"{start_date} to {end_date}",
        "transactions_checked": 150,
        "discrepancies": 2,
        "status": "completed"
    }


@celery_app.task
def generate_invoices(agency_id: int):
    """Generate monthly invoices for an agency."""
    # This would generate PDF invoices for the agency
    return {
        "agency_id": agency_id,
        "invoices_generated": 1,
        "total_amount": 5000.00,
        "invoice_numbers": ["INV-2025-07-001"]
    }


@celery_app.task
def calculate_commissions(model_id: int, month: str):
    """Calculate commissions for a model."""
    # This would calculate detailed commission breakdowns
    return {
        "model_id": model_id,
        "month": month,
        "gross_earnings": 10000.00,
        "platform_fees": 2000.00,
        "agency_commission": 800.00,
        "net_earnings": 7200.00
    }
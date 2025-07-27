"""
Payment gateway webhook endpoints.
"""
import logging
import hmac
import hashlib
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.financial.application.payment_gateway_service import PaymentGatewayService
from modules.financial.application.transaction_service import TransactionService
from modules.financial.domain.models import TransactionStatus
from modules.notifications.realtime.namespace import send_notification

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/coinbase")
async def handle_coinbase_webhook(
    request: Request,
    x_cc_webhook_signature: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Coinbase Commerce webhook events.
    
    Events handled:
    - charge:confirmed - Payment confirmed on blockchain
    - charge:failed - Payment failed
    - charge:delayed - Payment delayed
    - charge:resolved - Payment resolved after delay
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Verify webhook signature
        gateway_service = PaymentGatewayService(db)
        is_valid = await gateway_service.verify_webhook_signature(
            "coinbase",
            body,
            x_cc_webhook_signature
        )
        
        if not is_valid:
            logger.warning("Invalid Coinbase webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse webhook data
        data = await request.json()
        event_type = data.get("event", {}).get("type")
        event_data = data.get("event", {}).get("data", {})
        
        logger.info(f"Received Coinbase webhook: {event_type}")
        
        # Handle different event types
        if event_type == "charge:confirmed":
            await handle_payment_confirmed(db, "coinbase", event_data)
        elif event_type == "charge:failed":
            await handle_payment_failed(db, "coinbase", event_data)
        elif event_type == "charge:delayed":
            await handle_payment_delayed(db, "coinbase", event_data)
        elif event_type == "charge:resolved":
            await handle_payment_resolved(db, "coinbase", event_data)
        else:
            logger.info(f"Unhandled Coinbase event type: {event_type}")
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error processing Coinbase webhook: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.post("/bitpay")
async def handle_bitpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle BitPay webhook events.
    
    Events handled:
    - invoice_confirmed - Payment confirmed
    - invoice_completed - Payment completed
    - invoice_expired - Invoice expired
    - invoice_invalid - Invoice invalid
    """
    try:
        # Parse webhook data
        data = await request.json()
        
        # BitPay sends the event data directly
        event_type = data.get("event", {}).get("name")
        event_data = data.get("data", {})
        
        logger.info(f"Received BitPay webhook: {event_type}")
        
        # Verify webhook (BitPay uses different verification method)
        # In production, verify using BitPay's webhook signature
        
        # Handle different event types
        if event_type == "invoice_confirmed":
            await handle_payment_confirmed(db, "bitpay", event_data)
        elif event_type == "invoice_completed":
            await handle_payment_completed(db, "bitpay", event_data)
        elif event_type == "invoice_expired":
            await handle_payment_expired(db, "bitpay", event_data)
        elif event_type == "invoice_invalid":
            await handle_payment_failed(db, "bitpay", event_data)
        else:
            logger.info(f"Unhandled BitPay event type: {event_type}")
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error processing BitPay webhook: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


async def handle_payment_confirmed(
    db: AsyncSession,
    provider: str,
    event_data: Dict[str, Any]
):
    """Handle payment confirmation from any provider."""
    try:
        # Extract payment ID based on provider
        if provider == "coinbase":
            external_id = event_data.get("code")
            amount = event_data.get("pricing", {}).get("local", {}).get("amount")
            currency = event_data.get("pricing", {}).get("local", {}).get("currency")
        else:  # bitpay
            external_id = event_data.get("id")
            amount = event_data.get("price")
            currency = event_data.get("currency")
        
        if not external_id:
            logger.error(f"No external ID in {provider} webhook data")
            return
        
        # Find transaction by external reference
        transaction_service = TransactionService(db)
        transaction = await transaction_service.get_transaction_by_external_ref(external_id)
        
        if not transaction:
            logger.warning(f"Transaction not found for {provider} payment: {external_id}")
            return
        
        # Update transaction status
        transaction.status = TransactionStatus.COMPLETED
        transaction.processed_at = datetime.utcnow()
        transaction.metadata = transaction.metadata or {}
        transaction.metadata["webhook_confirmed"] = True
        transaction.metadata["confirmed_at"] = datetime.utcnow().isoformat()
        
        await db.commit()
        
        # Send real-time notification
        await send_notification(
            "payment_confirmed",
            {
                "transaction_id": str(transaction.id),
                "model_id": str(transaction.model_id),
                "amount": float(amount) if amount else float(transaction.amount),
                "currency": currency or transaction.currency,
                "provider": provider
            }
        )
        
        logger.info(f"Payment confirmed for transaction {transaction.id}")
        
    except Exception as e:
        logger.error(f"Error handling payment confirmation: {e}")
        await db.rollback()
        raise


async def handle_payment_failed(
    db: AsyncSession,
    provider: str,
    event_data: Dict[str, Any]
):
    """Handle payment failure from any provider."""
    try:
        # Extract payment ID
        external_id = event_data.get("code" if provider == "coinbase" else "id")
        
        if not external_id:
            return
        
        # Find and update transaction
        transaction_service = TransactionService(db)
        transaction = await transaction_service.get_transaction_by_external_ref(external_id)
        
        if transaction:
            transaction.status = TransactionStatus.FAILED
            transaction.metadata = transaction.metadata or {}
            transaction.metadata["failure_reason"] = event_data.get("failure_reason", "Payment failed")
            transaction.metadata["failed_at"] = datetime.utcnow().isoformat()
            
            await db.commit()
            
            # Send notification
            await send_notification(
                "payment_failed",
                {
                    "transaction_id": str(transaction.id),
                    "model_id": str(transaction.model_id),
                    "provider": provider,
                    "reason": transaction.metadata["failure_reason"]
                }
            )
            
            logger.info(f"Payment failed for transaction {transaction.id}")
            
    except Exception as e:
        logger.error(f"Error handling payment failure: {e}")
        await db.rollback()


async def handle_payment_delayed(
    db: AsyncSession,
    provider: str,
    event_data: Dict[str, Any]
):
    """Handle payment delay notification."""
    try:
        external_id = event_data.get("code" if provider == "coinbase" else "id")
        
        if not external_id:
            return
        
        # Find and update transaction
        transaction_service = TransactionService(db)
        transaction = await transaction_service.get_transaction_by_external_ref(external_id)
        
        if transaction:
            transaction.metadata = transaction.metadata or {}
            transaction.metadata["payment_delayed"] = True
            transaction.metadata["delayed_at"] = datetime.utcnow().isoformat()
            transaction.metadata["delay_reason"] = event_data.get("reason", "Payment processing delayed")
            
            await db.commit()
            
            # Send notification
            await send_notification(
                "payment_delayed",
                {
                    "transaction_id": str(transaction.id),
                    "model_id": str(transaction.model_id),
                    "provider": provider,
                    "reason": transaction.metadata["delay_reason"]
                }
            )
            
    except Exception as e:
        logger.error(f"Error handling payment delay: {e}")
        await db.rollback()


async def handle_payment_resolved(
    db: AsyncSession,
    provider: str,
    event_data: Dict[str, Any]
):
    """Handle payment resolution after delay."""
    # This is essentially the same as confirmed
    await handle_payment_confirmed(db, provider, event_data)


async def handle_payment_completed(
    db: AsyncSession,
    provider: str,
    event_data: Dict[str, Any]
):
    """Handle payment completion (BitPay specific)."""
    # For BitPay, completed means fully processed
    await handle_payment_confirmed(db, provider, event_data)


async def handle_payment_expired(
    db: AsyncSession,
    provider: str,
    event_data: Dict[str, Any]
):
    """Handle payment expiration."""
    try:
        external_id = event_data.get("id")
        
        if not external_id:
            return
        
        # Find and update transaction
        transaction_service = TransactionService(db)
        transaction = await transaction_service.get_transaction_by_external_ref(external_id)
        
        if transaction and transaction.status == TransactionStatus.PENDING:
            transaction.status = TransactionStatus.FAILED
            transaction.metadata = transaction.metadata or {}
            transaction.metadata["failure_reason"] = "Payment expired"
            transaction.metadata["expired_at"] = datetime.utcnow().isoformat()
            
            await db.commit()
            
            # Send notification
            await send_notification(
                "payment_expired",
                {
                    "transaction_id": str(transaction.id),
                    "model_id": str(transaction.model_id),
                    "provider": provider
                }
            )
            
    except Exception as e:
        logger.error(f"Error handling payment expiration: {e}")
        await db.rollback()


@router.post("/stripe")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Stripe webhook events.
    
    Reserved for future Stripe integration.
    """
    return {"status": "not_implemented"}


@router.post("/paypal")
async def handle_paypal_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle PayPal webhook events.
    
    Reserved for future PayPal integration.
    """
    return {"status": "not_implemented"}
"""
Stripe payment gateway implementation.

Handles Stripe payments, including card payments, bank transfers,
and crypto payments through Stripe's partners.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
import hmac
import hashlib
import json

import httpx
from fastapi import HTTPException

from .payment_gateway_base import (
    PaymentGatewayBase,
    PaymentRequest,
    PaymentResponse,
    PaymentStatus,
    WebhookData
)


logger = logging.getLogger(__name__)


class StripeGateway(PaymentGatewayBase):
    """Stripe payment gateway implementation."""
    
    BASE_URL = "https://api.stripe.com/v1"
    TEST_BASE_URL = "https://api.stripe.com/v1"  # Same for test mode
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Stripe gateway."""
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.webhook_secret = config.get('webhook_secret')
        self.base_url = self.TEST_BASE_URL if self.is_test_mode else self.BASE_URL
        
        # Validate configuration
        self.validate_config()
        
    def get_required_config_keys(self) -> List[str]:
        """Get required configuration keys."""
        return ['api_key', 'webhook_secret']
        
    async def create_payment(self, request: PaymentRequest) -> PaymentResponse:
        """
        Create a Stripe payment intent or checkout session.
        
        For crypto payments, this would create a checkout session
        with crypto payment methods enabled.
        """
        async with httpx.AsyncClient() as client:
            try:
                # Create a payment intent for direct API integration
                if request.recipient_email:
                    # Create checkout session for hosted payment page
                    response = await client.post(
                        f"{self.base_url}/checkout/sessions",
                        headers=self._get_headers(),
                        data={
                            'mode': 'payment',
                            'success_url': request.redirect_url or 'https://example.com/success',
                            'cancel_url': 'https://example.com/cancel',
                            'payment_method_types[]': ['card'],
                            'line_items[0][price_data][currency]': request.currency.lower(),
                            'line_items[0][price_data][unit_amount]': int(request.amount * 100),  # Stripe uses cents
                            'line_items[0][price_data][product_data][name]': request.description,
                            'line_items[0][quantity]': 1,
                            'customer_email': request.recipient_email,
                            'metadata': json.dumps(request.metadata or {})
                        }
                    )
                    
                    if response.status_code != 200:
                        raise Exception(f"Stripe API error: {response.text}")
                        
                    data = response.json()
                    
                    return PaymentResponse(
                        payment_id=data['id'],
                        provider_payment_id=data['id'],
                        status=self.map_status(data['payment_status'] or 'pending'),
                        amount=request.amount,
                        currency=request.currency,
                        payment_url=data['url'],
                        expires_at=datetime.utcnow() + timedelta(minutes=request.expires_minutes or 60),
                        metadata=request.metadata
                    )
                else:
                    # Create payment intent for API-based flow
                    response = await client.post(
                        f"{self.base_url}/payment_intents",
                        headers=self._get_headers(),
                        data={
                            'amount': int(request.amount * 100),
                            'currency': request.currency.lower(),
                            'description': request.description,
                            'metadata': json.dumps(request.metadata or {}),
                            'automatic_payment_methods[enabled]': 'true'
                        }
                    )
                    
                    if response.status_code != 200:
                        raise Exception(f"Stripe API error: {response.text}")
                        
                    data = response.json()
                    
                    return PaymentResponse(
                        payment_id=data['id'],
                        provider_payment_id=data['id'],
                        status=self.map_status(data['status']),
                        amount=request.amount,
                        currency=request.currency,
                        metadata=request.metadata
                    )
                    
            except Exception as e:
                logger.error(f"Stripe payment creation failed: {e}")
                raise
                
    async def get_payment_status(self, payment_id: str) -> PaymentResponse:
        """Get current status of a Stripe payment."""
        async with httpx.AsyncClient() as client:
            try:
                # Try as payment intent first
                response = await client.get(
                    f"{self.base_url}/payment_intents/{payment_id}",
                    headers=self._get_headers()
                )
                
                if response.status_code == 404:
                    # Try as checkout session
                    response = await client.get(
                        f"{self.base_url}/checkout/sessions/{payment_id}",
                        headers=self._get_headers()
                    )
                    
                if response.status_code != 200:
                    raise Exception(f"Payment not found: {payment_id}")
                    
                data = response.json()
                
                # Handle different response types
                if data['object'] == 'payment_intent':
                    return PaymentResponse(
                        payment_id=data['id'],
                        provider_payment_id=data['id'],
                        status=self.map_status(data['status']),
                        amount=Decimal(data['amount']) / 100,
                        currency=data['currency'].upper(),
                        metadata=data.get('metadata', {})
                    )
                else:  # checkout.session
                    return PaymentResponse(
                        payment_id=data['id'],
                        provider_payment_id=data['payment_intent'] or data['id'],
                        status=self.map_status(data['payment_status'] or 'pending'),
                        amount=Decimal(data['amount_total']) / 100,
                        currency=data['currency'].upper(),
                        payment_url=data.get('url'),
                        metadata=data.get('metadata', {})
                    )
                    
            except Exception as e:
                logger.error(f"Failed to get Stripe payment status: {e}")
                raise
                
    async def cancel_payment(self, payment_id: str) -> bool:
        """Cancel a Stripe payment intent."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/payment_intents/{payment_id}/cancel",
                    headers=self._get_headers()
                )
                
                return response.status_code == 200
                
            except Exception as e:
                logger.error(f"Failed to cancel Stripe payment: {e}")
                return False
                
    async def verify_webhook(
        self,
        headers: Dict[str, str],
        body: bytes,
        webhook_secret: str
    ) -> bool:
        """Verify Stripe webhook signature."""
        signature = headers.get('stripe-signature')
        if not signature:
            return False
            
        try:
            # Parse signature header
            timestamp = None
            signatures = []
            
            for element in signature.split(','):
                key, value = element.split('=')
                if key == 't':
                    timestamp = value
                elif key == 'v1':
                    signatures.append(value)
                    
            if not timestamp or not signatures:
                return False
                
            # Compute expected signature
            signed_payload = f"{timestamp}.{body.decode('utf-8')}"
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                signed_payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Check if any signature matches
            return any(
                hmac.compare_digest(expected_signature, sig)
                for sig in signatures
            )
            
        except Exception as e:
            logger.error(f"Webhook verification failed: {e}")
            return False
            
    async def parse_webhook(self, body: Dict[str, Any]) -> WebhookData:
        """Parse Stripe webhook data."""
        event_type = body.get('type', '')
        data = body.get('data', {}).get('object', {})
        
        # Map Stripe events to our event types
        event_map = {
            'payment_intent.succeeded': 'payment.completed',
            'payment_intent.payment_failed': 'payment.failed',
            'payment_intent.canceled': 'payment.cancelled',
            'checkout.session.completed': 'payment.completed',
            'checkout.session.expired': 'payment.expired'
        }
        
        # Extract payment ID based on object type
        if data.get('object') == 'payment_intent':
            payment_id = data['id']
            amount = Decimal(data['amount']) / 100
            currency = data['currency'].upper()
            status = self.map_status(data['status'])
        elif data.get('object') == 'checkout.session':
            payment_id = data['id']
            amount = Decimal(data['amount_total']) / 100
            currency = data['currency'].upper()
            status = self.map_status(data['payment_status'] or 'pending')
        else:
            raise ValueError(f"Unknown webhook object type: {data.get('object')}")
            
        return WebhookData(
            event_type=event_map.get(event_type, event_type),
            payment_id=payment_id,
            status=status,
            amount=amount,
            currency=currency,
            metadata=data.get('metadata', {})
        )
        
    async def get_supported_currencies(self) -> List[str]:
        """Get Stripe supported currencies."""
        # Stripe supports many currencies, here are the most common
        return [
            'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CNY',
            'CHF', 'HKD', 'NZD', 'SEK', 'DKK', 'NOK', 'SGD',
            'MXN', 'BRL', 'ARS', 'CLP', 'COP', 'PEN', 'UYU'
        ]
        
    async def get_exchange_rates(self, base_currency: str = "USD") -> Dict[str, Decimal]:
        """
        Get exchange rates.
        
        Note: Stripe doesn't provide exchange rates directly,
        so this would need to use another service or return
        fixed rates for supported currencies.
        """
        # For demo purposes, return some fixed rates
        rates = {
            'USD': Decimal('1.00'),
            'EUR': Decimal('0.85'),
            'GBP': Decimal('0.73'),
            'CAD': Decimal('1.25'),
            'AUD': Decimal('1.35')
        }
        
        if base_currency != 'USD':
            # Convert rates to different base
            base_rate = rates.get(base_currency, Decimal('1'))
            return {
                currency: rate / base_rate
                for currency, rate in rates.items()
            }
            
        return rates
        
    async def refund_payment(
        self,
        payment_id: str,
        amount: Optional[Decimal] = None,
        reason: Optional[str] = None
    ) -> bool:
        """Create a refund for a Stripe payment."""
        async with httpx.AsyncClient() as client:
            try:
                data = {'payment_intent': payment_id}
                
                if amount:
                    data['amount'] = int(amount * 100)
                    
                if reason:
                    # Map reason to Stripe's refund reasons
                    reason_map = {
                        'duplicate': 'duplicate',
                        'fraudulent': 'fraudulent',
                        'requested': 'requested_by_customer'
                    }
                    data['reason'] = reason_map.get(reason, 'requested_by_customer')
                    
                response = await client.post(
                    f"{self.base_url}/refunds",
                    headers=self._get_headers(),
                    data=data
                )
                
                return response.status_code == 200
                
            except Exception as e:
                logger.error(f"Failed to create Stripe refund: {e}")
                return False
                
    def map_status(self, stripe_status: str) -> PaymentStatus:
        """Map Stripe status to unified status."""
        status_map = {
            'requires_payment_method': PaymentStatus.PENDING,
            'requires_confirmation': PaymentStatus.PENDING,
            'requires_action': PaymentStatus.PENDING,
            'processing': PaymentStatus.PROCESSING,
            'requires_capture': PaymentStatus.PROCESSING,
            'succeeded': PaymentStatus.COMPLETED,
            'canceled': PaymentStatus.CANCELLED,
            'failed': PaymentStatus.FAILED,
            # Checkout session statuses
            'complete': PaymentStatus.COMPLETED,
            'expired': PaymentStatus.EXPIRED,
            'open': PaymentStatus.PENDING
        }
        
        return status_map.get(stripe_status, PaymentStatus.PENDING)
        
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Stripe API requests."""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Stripe-Version': '2023-10-16'  # Latest API version
        }
        
    async def create_payout(
        self,
        amount: Decimal,
        currency: str,
        destination: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a payout to a connected account or external account.
        
        This is used for paying out to models/agencies.
        """
        async with httpx.AsyncClient() as client:
            try:
                data = {
                    'amount': int(amount * 100),
                    'currency': currency.lower(),
                    'description': description,
                    'destination': destination,  # Bank account or debit card ID
                    'metadata': json.dumps(metadata or {})
                }
                
                response = await client.post(
                    f"{self.base_url}/payouts",
                    headers=self._get_headers(),
                    data=data
                )
                
                if response.status_code != 200:
                    raise Exception(f"Stripe payout failed: {response.text}")
                    
                return response.json()
                
            except Exception as e:
                logger.error(f"Failed to create Stripe payout: {e}")
                raise